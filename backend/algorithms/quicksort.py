"""QuickSort determinista vs. aleatorizado (W1 T2): cola de moderación ordenada por duración."""
from __future__ import annotations

import random
import statistics
import time


def quicksort(values, randomized: bool = False, seed: int = 42) -> list:
    """QuickSort iterativo in-place; pivote = último elemento o uno aleatorio."""
    a = list(values)
    rng = random.Random(seed)
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            if randomized:
                j = rng.randint(lo, hi)
                a[j], a[hi] = a[hi], a[j]
            pivot = a[hi]
            i = lo
            for j in range(lo, hi):
                if a[j] <= pivot:
                    a[i], a[j] = a[j], a[i]
                    i += 1
            a[i], a[hi] = a[hi], a[i]
            # procesa primero la partición pequeña para acotar la pila
            if i - lo < hi - i:
                if i + 1 < hi:
                    stack.append((i + 1, hi))
                hi = i - 1
            else:
                if lo < i - 1:
                    stack.append((lo, i - 1))
                lo = i + 1
    return a


def benchmark(durations: list[int], sizes=(500, 1000, 2000, 4000, 8000), reps: int = 2) -> list[dict]:
    """Mide ambos algoritmos en tres escenarios; verifica contra sorted() (conteo exacto)."""
    rows = []
    for n in sizes:
        base = durations[:n]
        scenarios = {"original": base, "ordenado": sorted(base), "inverso": sorted(base, reverse=True)}
        for scenario, vals in scenarios.items():
            expected = sorted(vals)
            for alg, randomized in (("determinista", False), ("aleatorizado", True)):
                times = []
                for trial in range(reps):
                    t0 = time.perf_counter()
                    out = quicksort(vals, randomized, seed=42 + trial)
                    times.append((time.perf_counter() - t0) * 1000)
                    assert out == expected, f"QuickSort falló: {scenario}/{alg}/n={n}"
                rows.append({"n": n, "scenario": scenario, "algorithm": alg,
                             "mean_ms": statistics.mean(times), "min_ms": min(times)})
    return rows
