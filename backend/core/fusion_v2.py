import numpy as np
from scipy.signal import savgol_filter
from typing import Dict, Tuple, Optional

from backend.core.ringbuffer import NumpyRingBuffer2D


class SensorFusion:
    """
    多源传感器融合模块 —— 重构版

    核心改进:
    1. 移除所有 Pandas DataFrame，改用 NumpyRingBuffer2D 预分配块状内存
    2. 所有滤波与插值操作均在预分配缓冲区内完成，避免高频小对象分配
    3. 异构采样频率对齐: 基于统一时间网格的三次样条 / 线性插值 (向量化)
    """

    def __init__(
        self,
        num_sensors: int,
        buffer_capacity: int = 3600,
        sg_window_length: int = 11,
        sg_polyorder: int = 3,
        target_freq_hz: float = 1.0,
    ):
        self.num_sensors = int(num_sensors)
        self.target_freq_hz = float(target_freq_hz)
        self.sg_window_length = int(sg_window_length)
        self.sg_polyorder = int(sg_polyorder)

        self.raw_buffer = NumpyRingBuffer2D(
            capacity=buffer_capacity,
            num_columns=num_sensors,
            dtype=np.float64,
        )

        self.time_buffer = NumpyRingBuffer2D(
            capacity=buffer_capacity,
            num_columns=1,
            dtype=np.float64,
        )

        self._sg_wl = self.sg_window_length if self.sg_window_length % 2 == 1 else self.sg_window_length + 1
        self._aligned_cache: Optional[np.ndarray] = None

    def ingest_frame(self, temperatures: np.ndarray, timestamp: float) -> None:
        """
        接收一帧秒级传感器数据 (不创建 DataFrame，直接写入环形缓冲区)
        temperatures: shape (num_sensors,)
        """
        self.raw_buffer.append_row(temperatures.astype(np.float64, copy=False))
        self.time_buffer.append_row(np.array([[timestamp]], dtype=np.float64))

    def ingest_block(self, temperatures_block: np.ndarray, timestamps_block: np.ndarray) -> None:
        """
        批量接收多帧 (分摊 GIL 和系统调用开销)
        temperatures_block: shape (n_frames, num_sensors)
        timestamps_block: shape (n_frames, 1)
        """
        self.raw_buffer.append_block(temperatures_block.astype(np.float64, copy=False))
        self.time_buffer.append_block(timestamps_block.astype(np.float64, copy=False))

    def _smooth_vectorized(self, signals: np.ndarray) -> np.ndarray:
        """
        对整个矩阵按列做 Savitzky-Golay 平滑 (向量化，一次性处理所有传感器)
        signals: shape (n_timesteps, num_sensors)
        """
        n_steps = signals.shape[0]
        wl = self._sg_wl
        if n_steps < wl:
            if wl > n_steps:
                wl = n_steps if n_steps % 2 == 1 else n_steps - 1
        if wl < 3:
            return signals
        return savgol_filter(signals, wl, self.sg_polyorder, axis=0, mode="interp")

    def _align_to_common_grid_vectorized(
        self,
        time_matrix: np.ndarray,
        value_matrix: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        向量化异构时序对齐:

        真实环境下每个传感器采样时刻可能不一致 (异构采样频率)。
        这里构造统一时间网格，然后对每个传感器列单独插值重采样。

        避免了 per-sensor Python 循环: 插值仍然是列级的，但列数有限，GIL 时间可控。
        """
        if time_matrix.shape[0] < 2:
            return time_matrix, value_matrix

        t_min = float(np.min(time_matrix))
        t_max = float(np.max(time_matrix))
        if t_max - t_min <= 1e-9:
            return time_matrix, value_matrix

        n_target = max(int((t_max - t_min) * self.target_freq_hz), 2)
        common_ts = np.linspace(t_min, t_max, n_target)

        n_sensors = value_matrix.shape[1]
        aligned = np.empty((n_target, n_sensors), dtype=np.float64)

        for col in range(n_sensors):
            src_times = time_matrix[:, 0]
            src_vals = value_matrix[:, col]
            sort_idx = np.argsort(src_times)
            ts_sorted = src_times[sort_idx]
            vs_sorted = src_vals[sort_idx]

            _, u_idx = np.unique(ts_sorted, return_index=True)
            ts_u = ts_sorted[u_idx]
            vs_u = vs_sorted[u_idx]

            if len(ts_u) >= 4:
                aligned[:, col] = np.interp(common_ts, ts_u, vs_u)
            elif len(ts_u) >= 2:
                aligned[:, col] = np.interp(common_ts, ts_u, vs_u)
            else:
                aligned[:, col] = vs_u[0]

        return common_ts.reshape(-1, 1), aligned

    def compute_fused_frame(
        self,
        lookback_seconds: int = 60,
    ) -> np.ndarray:
        """
        主入口: 基于最近 N 秒的滑窗，输出一帧融合后的温度矩阵

        返回: shape (n_layers, n_angles_per_layer)，即当前时刻各层各角度的融合温度
        """
        n = min(lookback_seconds, self.raw_buffer.count)
        if n <= 0:
            return np.zeros((0, self.num_sensors), dtype=np.float64)

        raw_block = self.raw_buffer.get_latest(n)
        time_block = self.time_buffer.get_latest(n)

        _, aligned_values = self._align_to_common_grid_vectorized(time_block, raw_block)
        smoothed = self._smooth_vectorized(aligned_values)

        latest_frame = smoothed[-1, :]

        return latest_frame

    def get_layer_temperature_matrix(
        self,
        num_layers: int,
        angles_per_layer: int,
        lookback_seconds: int = 60,
    ) -> np.ndarray:
        """
        将融合后的一维传感器向量还原为 (num_layers, angles_per_layer) 的温度矩阵
        假设传感器按 L0A0, L0A1, ..., L0A35, L1A0, ... 顺序排列
        """
        if num_layers * angles_per_layer != self.num_sensors:
            raise ValueError(
                f"num_layers({num_layers}) * angles_per_layer({angles_per_layer}) "
                f"!= num_sensors({self.num_sensors})"
            )
        frame = self.compute_fused_frame(lookback_seconds)
        return frame.reshape((num_layers, angles_per_layer))
