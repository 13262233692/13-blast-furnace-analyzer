import os
import signal
import time
import multiprocessing as mp
from multiprocessing import Process, Queue
from queue import Empty
from typing import Optional
import numpy as np

from backend.core.solver import HeatConductionSolver, RefractoryMaterial


# ---------------------------------------------------------------------------
# 子进程入口函数 —— 该函数在独立子进程中运行，完全脱离主进程的 GIL
# ---------------------------------------------------------------------------
def _pde_worker_loop(
    request_queue: Queue,
    response_queue: Queue,
    material_params: dict,
    solver_params: dict,
):
    """
    PDE 求解子进程主循环。

    完全隔离:
      - 不访问主进程的任何可变状态
      - 只通过两个 Queue 与主进程通信
      - 长时间数值计算（显式有限差分迭代）全部在此进程内，
        其 GIL 与主进程 GIL 互相独立，互不阻塞

    协议:
      req = {"id": str, "temps": np.ndarray (shape (layers, angles))}
      resp = {"id": str, "thickness_mm": np.ndarray (同 shape)}
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    material = RefractoryMaterial(**material_params)
    solver = HeatConductionSolver(material=material, **solver_params)

    while True:
        try:
            req = request_queue.get(timeout=5.0)
        except Empty:
            continue

        if req is None or req.get("__stop__"):
            break

        req_id = req["id"]
        temps: np.ndarray = req["temps"]

        thickness = solver.compute_thickness_batch(temps)

        try:
            response_queue.put_nowait({
                "id": req_id,
                "thickness_mm": thickness,
                "pid": os.getpid(),
                "ts": time.time(),
            })
        except Exception:
            # 响应队列满了 -> 丢弃，避免子进程被拖死
            pass


class PDEProcessManager:
    """
    PDE 求解子进程管理器 —— 主进程侧调用

    非阻塞设计:
      - submit(): 将温度矩阵推入请求队列，立即返回 (不等待求解)
      - poll_latest(): 从响应队列取最新结果，取不到就返回 None
      - 主处理线程 (API / simulator) 永远不会卡在 PDE 求解上
    """

    def __init__(
        self,
        material_params: dict = None,
        solver_params: dict = None,
        num_workers: int = 2,
        max_queue_size: int = 4,
    ):
        self.material_params = material_params or {
            "k": 1.5, "rho": 2400.0, "cp": 880.0, "original_thickness": 0.450,
        }
        self.solver_params = solver_params or {
            "h_gas": 25.0, "t_gas": 1200.0, "t_ambient": 30.0, "h_shell": 10.0,
        }
        self.num_workers = max(1, int(num_workers))
        self.max_queue_size = max_queue_size

        ctx = mp.get_context("spawn")
        self._request_q: Queue = ctx.Queue(maxsize=max_queue_size)
        self._response_q: Queue = ctx.Queue(maxsize=max_queue_size * 2)

        self._workers: list[Process] = []
        self._running = False
        self._latest_result: Optional[dict] = None
        self._request_counter = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for _ in range(self.num_workers):
            p = Process(
                target=_pde_worker_loop,
                args=(
                    self._request_q,
                    self._response_q,
                    self.material_params,
                    self.solver_params,
                ),
                daemon=True,
            )
            p.start()
            self._workers.append(p)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._workers:
            try:
                self._request_q.put_nowait({"__stop__": True})
            except Exception:
                pass
        deadline = time.time() + 5.0
        for p in self._workers:
            remaining = max(0.1, deadline - time.time())
            p.join(timeout=remaining)
            if p.is_alive():
                p.terminate()
        self._workers.clear()
        # 排空队列避免进程 hang
        for q in (self._request_q, self._response_q):
            try:
                while not q.empty():
                    q.get_nowait()
            except Exception:
                pass

    def submit(self, temps: np.ndarray) -> Optional[str]:
        """
        非阻塞提交一次 PDE 求解任务
        返回任务 id (如果队列满了就返回 None)
        """
        if not self._running:
            return None
        self._request_counter += 1
        req_id = f"req_{self._request_counter}"
        try:
            self._request_q.put_nowait({
                "id": req_id,
                "temps": np.ascontiguousarray(temps, dtype=np.float64),
            })
            return req_id
        except Exception:
            # 请求队列满 -> 丢弃旧任务
            try:
                self._request_q.get_nowait()
                self._request_q.put_nowait({
                    "id": req_id,
                    "temps": np.ascontiguousarray(temps, dtype=np.float64),
                })
                return req_id
            except Exception:
                return None

    def poll_latest(self) -> Optional[dict]:
        """
        非阻塞取最新结果 (消费全部响应，只保留最后一个)
        返回: {"id", "thickness_mm", "pid", "ts"} 或 None
        """
        result = self._latest_result
        try:
            while True:
                resp = self._response_q.get_nowait()
                result = resp
        except Empty:
            pass
        self._latest_result = result
        return result
