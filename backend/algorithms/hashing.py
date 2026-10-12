"""Hash tables (W1 T3/T4): sharding de uploaders y tabla por categoría con Chaining vs
Power of Two Choices."""
from __future__ import annotations

import hashlib
import math
import statistics


def stable_hash(value: str) -> int:
    """Hash de 64 bits determinista (independiente de PYTHONHASHSEED)."""
    return int.from_bytes(hashlib.sha256(str(value).encode("utf-8")).digest()[:8], "big")


def bucket_loads(keys: list[str], buckets: int, method: str) -> list[int]:
    """Inserta `keys` y devuelve la carga de cada bucket.

    - chaining:     bucket = h1(k) mod m
    - two_choices:  se elige el menos cargado entre h1(k) mod m y h2(k) mod m
    """
    loads = [0] * buckets
    for k in keys:
        a = stable_hash("A:" + k) % buckets
        if method == "chaining":
            chosen = a
        else:
            b = stable_hash("B:" + k) % buckets
            chosen = a if loads[a] <= loads[b] else b
        loads[chosen] += 1
    return loads


def theoretical_max_load(n: int, m: int, method: str) -> float:
    """Carga máxima esperada (aprox. asintótica) para n elementos en m buckets."""
    mu = n / m
    if method == "chaining":
        return mu + math.sqrt(2 * mu * math.log(m))          # cota tipo Chernoff
    return mu + math.log(math.log(m)) / math.log(2) + 1       # Azar et al.: ln ln m / ln 2 + O(1)


def histogram(loads: list[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for x in loads:
        out[x] = out.get(x, 0) + 1
    return out


def shard_uploaders(uploader_ids: list[str], workers: int = 32) -> dict:
    """W1 T3: reparte el trabajo de moderación entre `workers` revisores con hash(uploader_id)."""
    videos = [0] * workers
    users: list[set[str]] = [set() for _ in range(workers)]
    for u in uploader_ids:
        w = stable_hash(u) % workers
        videos[w] += 1
        users[w].add(u)
    distinct = [len(s) for s in users]
    n_users = sum(distinct)
    mean = len(uploader_ids) / workers
    return {
        "workers": workers,
        "videos": len(uploader_ids),
        "distinct_uploaders": n_users,
        # colisiones: uploaders que comparten revisor con otro uploader
        "collisions": int(sum(max(0, d - 1) for d in distinct)),
        "max_videos": max(videos),
        "min_videos": min(videos),
        "mean_videos": mean,
        "std_videos": statistics.pstdev(videos),
        "imbalance_ratio": max(videos) / mean,
        "videos_per_worker": videos,
    }
