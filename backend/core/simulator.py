import numpy as np
import time
import threading
from typing import Dict, List, Optional
from backend.core.fusion import SensorFusion
from backend.core.solver import HeatConductionSolver, RefractoryMaterial


NUM_LAYERS = 8
ANGLES_PER_LAYER = 36
SENSORS_PER_LAYER = ANGLES_PER_LAYER
TOTAL_SENSORS = NUM_LAYERS * SENSORS_PER_LAYER


class SensorSimulator:
    """
    高炉热电偶传感器数据模拟器
    模拟8层×36角度 = 288个热电偶传感器的实时数据流

    每层温度范围参考:
    - 炉身上部(Layer 0-1): 200-400°C
    - 炉身中部(Layer 2-3): 300-600°C
    - 炉腰(Layer 4-5): 400-700°C
    - 炉腹(Layer 6-7): 500-800°C

    侵蚀模拟: 某些角度位置的炉壳温度异常升高，暗示耐火砖变薄
    """

    LAYER_TEMP_RANGES = {
        0: (180, 260),
        1: (200, 290),
        2: (230, 330),
        3: (260, 370),
        4: (280, 400),
        5: (300, 430),
        6: (320, 460),
        7: (340, 490),
    }

    EROSION_ZONES = [
        {"layer": 3, "angle_range": (6, 12), "severity": 0.35},
        {"layer": 5, "angle_range": (18, 24), "severity": 0.50},
        {"layer": 6, "angle_range": (24, 30), "severity": 0.65},
        {"layer": 4, "angle_range": (10, 14), "severity": 0.25},
        {"layer": 7, "angle_range": (0, 6), "severity": 0.40},
    ]

    def __init__(self):
        self.fusion = SensorFusion(sg_window_length=11, sg_polyorder=3, target_freq_hz=1.0)
        self.solver = HeatConductionSolver(material=RefractoryMaterial())
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._current_data: Dict = {}
        self._tick = 0

        self._base_temps = self._init_base_temperatures()
        self._erosion_map = self._init_erosion_map()

    def _init_base_temperatures(self) -> np.ndarray:
        temps = np.zeros((NUM_LAYERS, ANGLES_PER_LAYER))
        for layer in range(NUM_LAYERS):
            t_low, t_high = self.LAYER_TEMP_RANGES[layer]
            base = np.random.uniform(t_low, t_high, ANGLES_PER_LAYER)
            for angle in range(ANGLES_PER_LAYER):
                phase = 2 * np.pi * angle / ANGLES_PER_LAYER
                base[angle] += 20 * np.sin(phase) + 10 * np.cos(3 * phase)
            temps[layer] = base
        return temps

    def _init_erosion_map(self) -> np.ndarray:
        erosion = np.zeros((NUM_LAYERS, ANGLES_PER_LAYER))
        for zone in self.EROSION_ZONES:
            layer = zone["layer"]
            a_start, a_end = zone["angle_range"]
            severity = zone["severity"]
            for a in range(a_start, a_end):
                t = (a - a_start) / max(a_end - a_start, 1)
                bell = np.exp(-((t - 0.5) ** 2) / 0.08) * severity
                erosion[layer, a] = max(erosion[layer, a], bell)
        return erosion

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _simulation_loop(self):
        while self.running:
            self._tick += 1
            data = self._generate_tick_data()
            with self._lock:
                self._current_data = data
            time.sleep(1.0)

    def _generate_tick_data(self) -> Dict:
        noise = np.random.normal(0, 5, (NUM_LAYERS, ANGLES_PER_LAYER))

        slow_drift = 10 * np.sin(self._tick * 0.05)
        temps = self._base_temps + noise + slow_drift

        erosion_boost = self._erosion_map * 250
        temps += erosion_boost

        temps = np.clip(temps, 40, 800)

        sensor_readings = []
        for layer in range(NUM_LAYERS):
            for angle in range(ANGLES_PER_LAYER):
                sensor_id = f"TC-L{layer}A{angle:02d}"
                sensor_readings.append(
                    {
                        "sensor_id": sensor_id,
                        "layer": layer,
                        "angle": angle * (360 // ANGLES_PER_LAYER),
                        "temperature": round(float(temps[layer, angle]), 2),
                        "timestamp": time.time(),
                    }
                )

        heatmap_data = temps.tolist()

        thickness_matrix = self.solver.compute_thickness_batch(temps)
        thickness_map = thickness_matrix.tolist()

        min_thickness = float(np.min(thickness_matrix))
        original_mm = self.solver.material.original_thickness * 1000
        max_erosion = float(np.max((original_mm - thickness_matrix) / original_mm))

        if max_erosion > 0.5:
            alert_level = "严重"
        elif max_erosion > 0.3:
            alert_level = "警告"
        elif max_erosion > 0.15:
            alert_level = "注意"
        else:
            alert_level = "正常"

        return {
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
            },
        }

    def get_current_data(self) -> Dict:
        with self._lock:
            return self._current_data.copy() if self._current_data else {}
