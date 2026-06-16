import numpy as np
import time
import threading
import multiprocessing as mp
from typing import Dict, Optional

from backend.core.fusion_v2 import SensorFusion
from backend.core.solver import HeatConductionSolver, RefractoryMaterial
from backend.core.pde_process import PDEProcessManager


NUM_LAYERS = 8
ANGLES_PER_LAYER = 36
SENSORS_PER_LAYER = ANGLES_PER_LAYER
TOTAL_SENSORS = NUM_LAYERS * SENSORS_PER_LAYER

BUFFER_CAPACITY = 3600
LOOKBACK_SECONDS = 60
PDE_SUBMIT_INTERVAL = 3


class SensorSimulatorV2:
    """
    高炉传感器模拟器 —— V2 高性能重构版

    数据流水线三段解耦:
      ┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
      │  Stage 1 数据注入    │────▶│  Stage 2 融合/重采样 │────▶│  Stage 3 PDE 子进程  │
      │  RingBuffer 原地写入 │     │  Numpy 块状运算       │     │  Multiprocessing 池  │
      │  零小对象分配        │     │  无 DataFrame         │     │  脱离主进程 GIL       │
      └──────────────────────┘     └──────────────────────┘     └──────────────────────┘

    主处理线程永远不会被 PDE 求解阻塞:
      - submit() 只是把温度矩阵塞进 Queue (非阻塞)
      - poll_latest() 每次取最新 PDE 结果 (取不到就用上次结果)
    """

    LAYER_TEMP_RANGES = {
        0: (180, 260), 1: (200, 290), 2: (230, 330), 3: (260, 370),
        4: (280, 400), 5: (300, 430), 6: (320, 460), 7: (340, 490),
    }

    EROSION_ZONES = [
        {"layer": 3, "angle_range": (6, 12), "severity": 0.35},
        {"layer": 5, "angle_range": (18, 24), "severity": 0.50},
        {"layer": 6, "angle_range": (24, 30), "severity": 0.65},
        {"layer": 4, "angle_range": (10, 14), "severity": 0.25},
        {"layer": 7, "angle_range": (0, 6), "severity": 0.40},
    ]

    def __init__(self):
        # --- Stage 2: 融合 + 重采样 ---
        self.fusion = SensorFusion(
            num_sensors=TOTAL_SENSORS,
            buffer_capacity=BUFFER_CAPACITY,
            sg_window_length=11,
            sg_polyorder=3,
            target_freq_hz=1.0,
        )

        # --- 本地同步求解器 (PDE 子进程冷启动时作为 fallback) ---
        self._fallback_solver = HeatConductionSolver(material=RefractoryMaterial())

        # --- Stage 3: PDE 子进程管理器 ---
        self.pde_manager = PDEProcessManager(
            material_params={
                "k": 1.5, "rho": 2400.0, "cp": 880.0, "original_thickness": 0.450,
            },
            solver_params={
                "h_gas": 25.0, "t_gas": 1200.0, "t_ambient": 30.0, "h_shell": 10.0,
            },
            num_workers=max(1, (mp.cpu_count() or 2) // 2),
            max_queue_size=4,
        )

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._current_data: Dict = {}
        self._tick = 0
        self._last_pde_submit = 0.0

        # --- 基础温度分布 (启动时一次性计算) ---
        self._base_temps = self._init_base_temperatures()
        self._erosion_map = self._init_erosion_map()

        # --- 最新 PDE 结果缓存 (原子读/写, 无需锁) ---
        self._latest_thickness: Optional[np.ndarray] = None
        self._solver_pid: Optional[int] = None

    def _init_base_temperatures(self) -> np.ndarray:
        temps = np.zeros((NUM_LAYERS, ANGLES_PER_LAYER), dtype=np.float64)
        angles = np.arange(ANGLES_PER_LAYER)
        for layer in range(NUM_LAYERS):
            t_low, t_high = self.LAYER_TEMP_RANGES[layer]
            base = np.random.uniform(t_low, t_high, ANGLES_PER_LAYER).astype(np.float64)
            phase = 2 * np.pi * angles / ANGLES_PER_LAYER
            base += 20.0 * np.sin(phase) + 10.0 * np.cos(3 * phase)
            temps[layer] = base
        return temps

    def _init_erosion_map(self) -> np.ndarray:
        erosion = np.zeros((NUM_LAYERS, ANGLES_PER_LAYER), dtype=np.float64)
        for zone in self.EROSION_ZONES:
            layer = zone["layer"]
            a_start, a_end = zone["angle_range"]
            severity = zone["severity"]
            a_indices = np.arange(a_start, a_end)
            t_vals = (a_indices - a_start) / max(a_end - a_start, 1)
            bell = np.exp(-((t_vals - 0.5) ** 2) / 0.08) * severity
            erosion[layer, a_indices] = np.maximum(erosion[layer, a_indices], bell)
        return erosion

    def start(self):
        if self.running:
            return
        self.running = True
        self.pde_manager.start()

        initial = self._generate_raw_frame()
        fallback_thickness = self._fallback_solver.compute_thickness_batch(initial)
        self._latest_thickness = fallback_thickness

        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)
        self.pde_manager.stop()

    def _simulation_loop(self):
        while self.running:
            self._tick += 1
            now = time.time()

            # -------------------------------------------------------
            # Stage 1: 生成一帧原始数据 + 写入环形缓冲区
            # -------------------------------------------------------
            raw_frame_2d = self._generate_raw_frame()
            raw_flat = raw_frame_2d.reshape(1, TOTAL_SENSORS)
            self.fusion.ingest_block(raw_flat, np.array([[now]], dtype=np.float64))

            # -------------------------------------------------------
            # Stage 2: 从 RingBuffer 取最近 LOOKBACK_SECONDS 秒数据,
            #          做对齐 + Savitzky-Golay 平滑
            # -------------------------------------------------------
            try:
                fused_2d = self.fusion.get_layer_temperature_matrix(
                    NUM_LAYERS, ANGLES_PER_LAYER, LOOKBACK_SECONDS
                )
            except Exception:
                fused_2d = raw_frame_2d

            fused_clipped = np.clip(fused_2d, 40.0, 800.0)

            # -------------------------------------------------------
            # Stage 3: 每隔 PDE_SUBMIT_INTERVAL 秒异步提交给子进程
            # -------------------------------------------------------
            if (now - self._last_pde_submit) >= PDE_SUBMIT_INTERVAL:
                req_id = self.pde_manager.submit(fused_clipped)
                if req_id is not None:
                    self._last_pde_submit = now

            # -------------------------------------------------------
            # 尝试从 PDE 子进程取回最新结果 (完全非阻塞)
            # 没有新结果就继续用上次缓存
            # -------------------------------------------------------
            pde_resp = self.pde_manager.poll_latest()
            if pde_resp is not None:
                self._latest_thickness = pde_resp["thickness_mm"]
                self._solver_pid = pde_resp.get("pid")

            thickness_2d = self._latest_thickness
            if thickness_2d is None:
                thickness_2d = self._fallback_solver.compute_thickness_batch(fused_clipped)
                self._latest_thickness = thickness_2d

            # -------------------------------------------------------
            # 组装对外暴露的数据
            # -------------------------------------------------------
            sensor_readings = self._flatten_to_readings(fused_clipped, now)
            heatmap_data = fused_clipped.tolist()
            thickness_map = thickness_2d.tolist()

            min_thickness = float(np.min(thickness_2d))
            original_mm = self._fallback_solver.material.original_thickness * 1000.0
            max_erosion = float(np.max((original_mm - thickness_2d) / original_mm))

            if max_erosion > 0.5:
                alert_level = "严重"
            elif max_erosion > 0.3:
                alert_level = "警告"
            elif max_erosion > 0.15:
                alert_level = "注意"
            else:
                alert_level = "正常"

            with self._lock:
                self._current_data = {
                    "sensors": sensor_readings,
                    "heatmap": heatmap_data,
                    "thickness_map": thickness_map,
                    "status": {
                        "total_sensors": TOTAL_SENSORS,
                        "active_sensors": TOTAL_SENSORS,
                        "min_thickness_mm": round(min_thickness, 1),
                        "max_erosion_ratio": round(max_erosion, 4),
                        "alert_level": alert_level,
                        "tick": self._tick,
                        "pde_worker_pid": self._solver_pid,
                        "buffer_count": self.fusion.raw_buffer.count,
                    },
                }

            time.sleep(1.0)

    def _generate_raw_frame(self) -> np.ndarray:
        """生成一帧原始温度矩阵 (8 x 36)，纯 NumPy 运算"""
        noise = np.random.normal(0, 5, (NUM_LAYERS, ANGLES_PER_LAYER))
        slow_drift = 10.0 * np.sin(self._tick * 0.05)
        frame = self._base_temps + noise + slow_drift + self._erosion_map * 250.0
        return frame

    def _flatten_to_readings(self, temps_2d: np.ndarray, now: float) -> list:
        readings = []
        for layer in range(NUM_LAYERS):
            for angle in range(ANGLES_PER_LAYER):
                sensor_id = f"TC-L{layer}A{angle:02d}"
                readings.append({
                    "sensor_id": sensor_id,
                    "layer": layer,
                    "angle": angle * (360 // ANGLES_PER_LAYER),
                    "temperature": round(float(temps_2d[layer, angle]), 2),
                    "timestamp": now,
                })
        return readings

    def get_current_data(self) -> Dict:
        with self._lock:
            if not self._current_data:
                return {}
            # 浅拷贝即可 (内部列表不再修改)
            return dict(self._current_data)
