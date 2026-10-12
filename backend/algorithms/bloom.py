"""Bloom filter de uploader_id ya marcados (W2 T2)."""
from __future__ import annotations

import hashlib
import math


class BloomFilter:
    def __init__(self, bits: int, hashes: int):
        if bits <= 0 or hashes <= 0:
            raise ValueError("bits y hashes deben ser positivos")
        self.bits, self.hashes = bits, hashes
        self.vector = bytearray((bits + 7) // 8)
        self.items = 0

    def _indices(self, value: str):
        d = hashlib.sha256(value.encode("utf-8")).digest()
        h1 = int.from_bytes(d[:8], "big")
        h2 = int.from_bytes(d[8:16], "big") | 1
        for i in range(self.hashes):
            yield (h1 + i * h2) % self.bits  # doble hashing de Kirsch-Mitzenmacher

    def add(self, value: str) -> None:
        for idx in self._indices(value):
            self.vector[idx // 8] |= 1 << (idx % 8)
        self.items += 1

    def __contains__(self, value: str) -> bool:
        return all(self.vector[idx // 8] & (1 << (idx % 8)) for idx in self._indices(value))

    def theoretical_fp(self, n: int | None = None) -> float:
        """(1 - e^{-kn/m})^k con n = elementos insertados (por defecto, los actuales)."""
        n = self.items if n is None else n
        return (1 - math.exp(-self.hashes * n / self.bits)) ** self.hashes


def sized_filter(capacity: int, bits_per_element: int) -> BloomFilter:
    """m = b·n bits y k = round(b·ln 2) funciones hash (k óptimo)."""
    m = max(1, capacity * bits_per_element)
    k = max(1, round(bits_per_element * math.log(2)))
    return BloomFilter(m, k)
