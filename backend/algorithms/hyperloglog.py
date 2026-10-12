"""HyperLogLog para el conteo de uploader_id distintos por día (W2 T4)."""
from __future__ import annotations

import math


class HyperLogLog:
    """m registros (potencia de 2). Error estándar teórico ≈ 1.04/√m; memoria ≈ 6·m bits."""

    def __init__(self, m: int):
        if m < 16 or m & (m - 1):
            raise ValueError("m debe ser potencia de 2 y >= 16")
        self.m = m
        self.p = m.bit_length() - 1
        self.registers = [0] * m

    def add_hash(self, h: int) -> None:
        """`h` es un hash de 64 bits ya calculado."""
        idx = h >> (64 - self.p)
        w = h & ((1 << (64 - self.p)) - 1)
        rho = (64 - self.p) - w.bit_length() + 1   # posición del primer 1
        if rho > self.registers[idx]:
            self.registers[idx] = rho

    def estimate(self) -> float:
        m = self.m
        alpha = {16: 0.673, 32: 0.697, 64: 0.709}.get(m, 0.7213 / (1 + 1.079 / m))
        e = alpha * m * m / sum(2.0 ** -r for r in self.registers)
        zeros = self.registers.count(0)
        if e <= 2.5 * m and zeros:                  # corrección de rango pequeño
            e = m * math.log(m / zeros)
        return e

    @property
    def memory_bits(self) -> int:
        return 6 * self.m

    @property
    def theoretical_error(self) -> float:
        return 1.04 / math.sqrt(self.m)
