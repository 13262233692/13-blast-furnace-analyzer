import numpy as np
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
from typing import Dict, List, Tuple


class SensorFusion:
    """
    多源传感器融合模块：
    1. Savitzky-Golay 滤波器平滑去噪
    2. 异构采样频率时序信号对齐（线性插值重采样）
    """

    def __init__(
        self,
        sg_window_length: int = 11,
        sg_polyorder: int = 3,
        target_freq_hz: float = 1.0,
    ):
        self.sg_window_length = sg_window_length
        self.sg_polyorder = sg_polyorder
        self.target_freq_hz = target_freq_hz

    def smooth(self, signal: np.ndarray) -> np.ndarray:
        if len(signal) < self.sg_window_length:
            return signal.copy()
        wl = self.sg_window_length if self.sg_window_length % 2 == 1 else self.sg_window_length + 1
        if wl > len(signal):
            wl = len(signal) if len(signal) % 2 == 1 else len(signal) - 1
        if wl < 3:
            return signal.copy()
        return savgol_filter(signal, wl, self.sg_polyorder)

    def align_time_series(
        self,
        signals: Dict[str, Tuple[np.ndarray, np.ndarray]],
    ) -> Dict[str, np.ndarray]:
        """
        signals: {sensor_id: (timestamps, values)}
        returns: {sensor_id: aligned_values}  对齐到公共时间轴
        """
        if not signals:
            return {}

        all_t_min = min(ts[0] for ts, _ in signals.values())
        all_t_max = max(ts[-1] for ts, _ in signals.values())
        duration = all_t_max - all_t_min
        if duration <= 0:
            return {k: v.copy() for k, (_, v) in signals.items()}

        n_points = max(int(duration * self.target_freq_hz), 2)
        common_ts = np.linspace(all_t_min, all_t_max, n_points)

        aligned = {}
        for sensor_id, (timestamps, values) in signals.items():
            if len(timestamps) < 2:
                aligned[sensor_id] = np.full(n_points, values[0] if len(values) > 0 else 0.0)
                continue
            kind = "linear"
            if len(timestamps) >= 4:
                kind = "cubic"
            interp_func = interp1d(
                timestamps, values, kind=kind, fill_value="extrapolate"
            )
            resampled = interp_func(common_ts)
            smoothed = self.smooth(resampled)
            aligned[sensor_id] = smoothed

        return aligned

    def fuse_layer_data(
        self,
        layer_temperatures: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """
        将同一层多个传感器的对齐后温度数据融合为该层的平均温度序列
        """
        if not layer_temperatures:
            return np.array([])
        arrays = list(layer_temperatures.values())
        min_len = min(len(a) for a in arrays)
        trimmed = [a[:min_len] for a in arrays]
        stacked = np.stack(trimmed, axis=0)
        return np.mean(stacked, axis=0)
