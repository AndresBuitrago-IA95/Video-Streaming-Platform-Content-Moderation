"""Reservoir sampling (Algoritmo R) para estimar view_count_1h promedio por categoría (W2 T3)."""
from __future__ import annotations

import random
from collections import defaultdict


def reservoir_sample(stream, k: int, rng: random.Random) -> list:
    """Muestra uniforme de tamaño k de un flujo de longitud desconocida, en una pasada."""
    sample: list = []
    for i, item in enumerate(stream):
        if i < k:
            sample.append(item)
        else:
            j = rng.randint(0, i)
            if j < k:
                sample[j] = item
    return sample


def mean_by_category(records) -> dict[str, float]:
    acc: dict[str, list[float]] = defaultdict(list)
    for category, value in records:
        acc[category].append(value)
    return {c: sum(v) / len(v) for c, v in acc.items()}


def compare_sizes(records: list[tuple[str, float]], sizes=(100, 300, 500), trials: int = 30,
                  seed: int = 42) -> list[dict]:
    """Para cada tamaño: error por categoría de una corrida + error medio sobre `trials` corridas."""
    exact = mean_by_category(records)
    rows = []
    for k in sizes:
        rng = random.Random(seed)
        first = mean_by_category(reservoir_sample(records, k, rng))
        errs = []
        for t in range(trials):
            est = mean_by_category(reservoir_sample(records, k, random.Random(seed + 1 + t)))
            errs.append(sum(abs(est.get(c, 0) - exact[c]) / exact[c] for c in exact) / len(exact))
        rows.append({
            "sample_size": k,
            "mean_error_pct_over_trials": 100 * sum(errs) / len(errs),
            "categories": [{"category": c, "exact": exact[c], "estimated": first.get(c),
                            "error_pct": 100 * abs(first.get(c, 0) - exact[c]) / exact[c]}
                           for c in sorted(exact)],
        })
    return rows
