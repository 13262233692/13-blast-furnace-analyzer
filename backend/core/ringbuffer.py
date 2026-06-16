import numpy as np
from typing import Tuple, Optional


class NumpyRingBuffer2D:
    """
    基于 NumPy 预分配内存的二维环形缓冲区

    内存布局: (buffer_capacity, num_columns)
      - 行维度: 时间步 (每一行代表一帧数据, 如某一秒所有传感器读数)
      - 列维度: 传感器通道 (每一列代表一个传感器的时间序列)

    零拷贝设计: 不创建任何小对象，所有操作都是原地内存覆盖 + 基于视图的切片
    """

    __slots__ = ("_buf", "_capacity", "_num_cols", "_head", "_count", "_dtype")

    def __init__(
        self,
        capacity: int,
        num_columns: int,
        dtype: np.dtype = np.float64,
    ):
        self._capacity = int(capacity)
        self._num_cols = int(num_columns)
        self._dtype = dtype
        self._buf = np.zeros((self._capacity, self._num_cols), dtype=dtype)
        self._head = 0
        self._count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def num_columns(self) -> int:
        return self._num_cols

    @property
    def count(self) -> int:
        return self._count

    @property
    def is_full(self) -> bool:
        return self._count >= self._capacity

    def reset(self) -> None:
        self._head = 0
        self._count = 0
        self._buf.fill(0.0)

    def append_row(self, row: np.ndarray) -> None:
        """
        原地写入一行 (一帧传感器数据)
        row: shape (num_columns,) 的一维 ndarray
        """
        if row.shape[0] != self._num_cols:
            raise ValueError(
                f"row shape mismatch: expected {self._num_cols}, got {row.shape[0]}"
            )
        self._buf[self._head, :] = row
        self._head = (self._head + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    def append_block(self, block: np.ndarray) -> None:
        """
        批量写入多行 (块写入，进一步分摊 GIL 开销)
        block: shape (n_rows, num_columns)
        """
        n = block.shape[0]
        if block.shape[1] != self._num_cols:
            raise ValueError("block columns mismatch")
        if n >= self._capacity:
            self._buf[:, :] = block[-self._capacity:, :]
            self._head = 0
            self._count = self._capacity
            return
        end = self._head + n
        if end <= self._capacity:
            self._buf[self._head:end, :] = block
            self._head = end % self._capacity
        else:
            k = self._capacity - self._head
            self._buf[self._head:, :] = block[:k, :]
            self._buf[:n - k, :] = block[k:, :]
            self._head = n - k
        self._count = min(self._count + n, self._capacity)

    def get_latest(self, n: Optional[int] = None) -> np.ndarray:
        """
        获取最近 N 行数据的 CONTIGUOUS 副本 (供下游算法消费)
        返回 shape: (min(n, count), num_columns)
        保证时间序由旧到新
        """
        if n is None:
            n = self._count
        n = min(n, self._count)
        if n <= 0:
            return np.empty((0, self._num_cols), dtype=self._dtype)
        start = (self._head - n) % self._capacity
        end = start + n
        if end <= self._capacity:
            return self._buf[start:end, :].copy()
        k = self._capacity - start
        result = np.empty((n, self._num_cols), dtype=self._dtype)
        result[:k, :] = self._buf[start:, :]
        result[k:, :] = self._buf[:n - k, :]
        return result

    def get_column(self, col_idx: int, n: Optional[int] = None) -> np.ndarray:
        """
        获取某一传感器 (列) 的最近 N 个连续时间序列 (一维)
        零额外分配：结果是一个一维 ndarray 副本
        """
        if not (0 <= col_idx < self._num_cols):
            raise IndexError(f"col_idx {col_idx} out of range [0, {self._num_cols})")
        return self.get_latest(n)[:, col_idx]

    def mean(self, n: Optional[int] = None, axis: int = 0) -> np.ndarray:
        """块状统计 - 直接视图计算，无中间对象"""
        data = self.get_latest(n)
        if data.size == 0:
            return np.zeros(self._num_cols, dtype=self._dtype)
        return np.mean(data, axis=axis)

    def __repr__(self) -> str:
        return (
            f"NumpyRingBuffer2D(cap={self._capacity}, cols={self._num_cols}, "
            f"count={self._count}, head={self._head})"
        )
