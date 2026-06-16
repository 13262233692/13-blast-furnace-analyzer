import numpy as np
from dataclasses import dataclass


@dataclass
class RefractoryMaterial:
    """
    耐火材料热物性参数
    """
    k: float = 1.5          # 导热系数 W/(m·K)
    rho: float = 2400.0     # 密度 kg/m³
    cp: float = 880.0       # 比热容 J/(kg·K)
    original_thickness: float = 0.450  # 原始耐火砖厚度 m (450mm)

    @property
    def alpha(self) -> float:
        return self.k / (self.rho * self.cp)


class HeatConductionSolver:
    """
    一维瞬态热传导方程求解器
    基于傅里叶热传导定律，采用显式有限差分法(Explicit Finite Difference)

    ∂T/∂t = α · ∂²T/∂x²

    边界条件:
    - x=0 (炉壳外表面): 已知温度 T_shell (由热电偶测量)
    - x=L (炉墙内表面): 对流换热边界 q = h*(T_gas - T_inner)

    反向推导逻辑:
    在稳态条件下，一维热传导的解析解为线性分布:
        T(x) = T_shell + (q/k) * x
    其中 q = h*(T_gas - T_inner) 为热流密度

    通过迭代搜索剩余耐火砖厚度 d_remain，使得在稳态下
    计算得到的炉壳外表面温度与实测值匹配。
    """

    def __init__(
        self,
        material: RefractoryMaterial = None,
        h_gas: float = 25.0,         # 炉内对流换热系数 W/(m²·K)
        t_gas: float = 1200.0,       # 炉内气相温度 °C
        t_ambient: float = 30.0,     # 环境温度 °C
        h_shell: float = 10.0,       # 炉壳外表面换热系数 W/(m²·K)
    ):
        self.material = material or RefractoryMaterial()
        self.h_gas = h_gas
        self.t_gas = t_gas
        self.t_ambient = t_ambient
        self.h_shell = h_shell

    def solve_transient_1d(
        self,
        t_shell_measured: float,
        d_remain: float,
        nx: int = 50,
        time_steps: int = 2000,
    ) -> np.ndarray:
        alpha = self.material.alpha
        k = self.material.k
        dx = d_remain / (nx - 1)
        dt = 0.4 * dx * dx / alpha
        r = alpha * dt / (dx * dx)

        T = np.linspace(t_shell_measured, self.t_gas * 0.8, nx)

        for _ in range(time_steps):
            T_new = T.copy()
            T_new[1:-1] = T[1:-1] + r * (T[2:] - 2 * T[1:-1] + T[:-2])
            T_new[0] = t_shell_measured

            q_in = self.h_gas * (self.t_gas - T_new[-1])
            T_new[-1] = T_new[-1] + dt * (
                r * 2 * (T_new[-2] - T_new[-1]) / 1
                + q_in / (self.material.rho * self.material.cp * dx)
            )

            T = T_new

        return T

    def compute_remaining_thickness(
        self,
        t_shell_measured: float,
        thickness_min: float = 0.05,
        thickness_max: float = 0.50,
        tolerance: float = 0.001,
        max_iter: int = 50,
        include_pde: bool = False,
    ) -> dict:
        """
        反向推导计算炉墙剩余耐火砖厚度

        原理：稳态一维热传导中，炉壳温度与耐火砖厚度存在单调关系。
        厚度越小 → 热阻越小 → 炉壳温度越高。

        采用二分法搜索：找到使得稳态炉壳外表面温度 ≈ 实测温度的剩余厚度。

        稳态解析近似:
        总热阻 R_total = 1/h_shell + d/k + 1/h_gas
        热流密度 q = (T_gas - T_ambient) / R_total
        炉壳温度 T_shell = T_ambient + q / h_shell
        """

        k = self.material.k
        d_low = thickness_min
        d_high = thickness_max

        for _ in range(max_iter):
            d_mid = (d_low + d_high) / 2.0

            r_total = 1.0 / self.h_shell + d_mid / k + 1.0 / self.h_gas
            q = (self.t_gas - self.t_ambient) / r_total
            t_shell_calc = self.t_ambient + q / self.h_shell

            if abs(t_shell_calc - t_shell_measured) < tolerance:
                break

            if t_shell_calc > t_shell_measured:
                d_low = d_mid
            else:
                d_high = d_mid

        d_remain = (d_low + d_high) / 2.0
        r_total = 1.0 / self.h_shell + d_remain / k + 1.0 / self.h_gas
        q = (self.t_gas - self.t_ambient) / r_total

        result = {
            "remaining_thickness_m": round(d_remain, 4),
            "remaining_thickness_mm": round(d_remain * 1000, 1),
            "original_thickness_mm": round(self.material.original_thickness * 1000, 1),
            "erosion_mm": round((self.material.original_thickness - d_remain) * 1000, 1),
            "erosion_ratio": round(
                (self.material.original_thickness - d_remain) / self.material.original_thickness, 4
            ),
            "heat_flux_w_m2": round(q, 1),
            "thermal_resistance": round(r_total, 6),
            "t_shell_calc": round(t_shell_calc, 2),
        }

        if include_pde:
            nx = 50
            T_distribution = self.solve_transient_1d(t_shell_measured, d_remain, nx=nx, time_steps=3000)
            result["temperature_distribution"] = T_distribution.tolist()
            result["x_positions_mm"] = np.linspace(0, d_remain * 1000, nx).tolist()

        return result

    def compute_layer_thickness_map(
        self,
        shell_temps: np.ndarray,
    ) -> dict:
        n_angles = len(shell_temps)
        results = []
        for i, t in enumerate(shell_temps):
            res = self.compute_remaining_thickness(float(t))
            results.append(
                {
                    "angle": i * (360 // n_angles),
                    **res,
                }
            )
        return results

    def compute_thickness_batch(
        self,
        shell_temps: np.ndarray,
        thickness_min: float = 0.05,
        thickness_max: float = 0.50,
        tolerance: float = 0.001,
        max_iter: int = 50,
    ) -> np.ndarray:
        """
        向量化批量计算：对整个温度矩阵一次性用二分法求解残厚
        shell_temps: 任意形状的温度数组
        返回: 同形状的残厚数组 (mm)
        """
        k = self.material.k
        d_low = np.full_like(shell_temps, thickness_min, dtype=float)
        d_high = np.full_like(shell_temps, thickness_max, dtype=float)

        for _ in range(max_iter):
            d_mid = (d_low + d_high) / 2.0
            r_total = 1.0 / self.h_shell + d_mid / k + 1.0 / self.h_gas
            q = (self.t_gas - self.t_ambient) / r_total
            t_shell_calc = self.t_ambient + q / self.h_shell

            mask_high = t_shell_calc > shell_temps
            d_low = np.where(mask_high, d_mid, d_low)
            d_high = np.where(~mask_high, d_mid, d_high)

            if np.max(np.abs(t_shell_calc - shell_temps)) < tolerance:
                break

        d_remain = (d_low + d_high) / 2.0
        return np.round(d_remain * 1000, 1)
