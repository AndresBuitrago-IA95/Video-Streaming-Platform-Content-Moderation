"""Motor MapReduce paralelo y experimentos del Workshop 4 (Unidad 4).

Implementa:
  - Runner MapReduce reutilizable con fase Map paralela sobre >=8 archivos fragmento
    usando ProcessPoolExecutor (>=2 workers), Combiner opcional por mapper,
    particionamiento a R reducers y medición exacta de tráfico shuffle (pares y bytes),
    tamaño máximo de reducer (q), tasa de replicación (r) y balance de carga.
  - Task 1: Job 1 (construcción del grafo de transiciones por uploader) y Job 2
    (resumen de nodos: out_transition_count, in_transition_count, net_flow,
    flagged_frac, avg_view_count_1h), validado contra Unidad 3.
  - Task 2 (S10): PageRank iterativo por multiplicación matriz-vector en MapReduce,
    validado contra Unidad 3 dentro de 1e-4.
  - Task 3: Análisis de costo — tamaño de shuffle con/sin combiner, escalamiento
    1x (100k), 2x (200k), 4x (400k), verificación de crecimiento lineal,
    extrapolación a 10x (1M) y costo S10 (pares/iteración × iteraciones).
  - Task 4: Tamaño de reducer (q) y tasa de replicación (r) por job, clave caliente
    (uploader más activo) y sensibilidad de Job 1 para R = 1, 2, 4, 8 reducers.
  - Task 5 (S14): Inyección de ola de spam (>=40% en una categoría), medición de
    load balance factor, speedup y eficiencia paralela para P = 1, 2, 4, 8, y
    mitigación mediante salting + combiner.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from config import EDGES_W4, FRAGMENTS_W4_DIR, NODE_SUMMARY_W4

CATEGORIES = (
    "Ciencia",
    "Cocina",
    "Deportes",
    "Educacion",
    "Entretenimiento",
    "Musica",
    "Noticias",
    "Salud",
    "Tecnologia",
    "Videojuegos",
)

FLAG_PROBABILITY = {
    "Ciencia": 0.10,
    "Cocina": 0.09,
    "Deportes": 0.11,
    "Educacion": 0.08,
    "Entretenimiento": 0.12,
    "Musica": 0.09,
    "Noticias": 0.13,
    "Salud": 0.12,
    "Tecnologia": 0.10,
    "Videojuegos": 0.11,
}


def _stable_partition(key: Any, num_reducers: int) -> int:
    if num_reducers <= 1:
        return 0
    digest = hashlib.blake2b(repr(key).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % num_reducers


def _estimate_pair_bytes(key: Any, value: Any) -> int:
    return len(json.dumps([key, value], separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Funciones top-level (picklables en Windows para ProcessPoolExecutor)
# --------------------------------------------------------------------------- #
def _noop_warmup(_: int) -> int:
    return 1


def _map_file_job1a(args: tuple[str, bool]) -> dict[str, Any]:
    """Job 1a Map: lee fragmento JSONL y emite (uploader_id, (seq, cat, flagged, views))."""
    path_str, _use_combiner = args
    pairs: list[tuple[str, tuple[int, str, int, float]]] = []
    input_records = 0
    with open(path_str, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            input_records += 1
            pairs.append((
                row["uploader_id"],
                (
                    int(row["stream_seq"]),
                    row["category"],
                    1 if row["is_flagged"] else 0,
                    float(row["view_count_1h"]),
                ),
            ))
    shuffle_bytes = sum(len(k) + 32 + len(v[1]) for k, v in pairs)
    return {
        "input_records": input_records,
        "map_output_pairs": len(pairs),
        "shuffle_pairs": len(pairs),
        "shuffle_bytes": shuffle_bytes,
        "pairs": pairs,
    }


def _reduce_bucket_job1a(bucket_items: list[tuple[str, tuple[int, str, int, float]]]) -> dict[str, Any]:
    """Job 1a Reduce: agrupa por uploader_id, ordena por stream_seq y emite pares consecutivos."""
    by_user: dict[str, list[tuple[int, str, int, float]]] = defaultdict(list)
    for uploader_id, val in bucket_items:
        by_user[uploader_id].append(val)

    edge_events: list[tuple[tuple[str, str], tuple[int, int, float]]] = []
    max_key_load = 0
    hot_key = ""
    for uploader_id, seq_vals in by_user.items():
        cnt = len(seq_vals)
        if cnt > max_key_load:
            max_key_load = cnt
            hot_key = uploader_id
        if cnt < 2:
            continue
        seq_vals.sort(key=lambda x: x[0])
        for i in range(cnt - 1):
            src_cat = seq_vals[i][1]
            _, dst_cat, dst_flag, dst_views = seq_vals[i + 1]
            edge_events.append(((src_cat, dst_cat), (1, dst_flag, dst_views)))

    return {
        "edge_events": edge_events,
        "max_key_load": max_key_load,
        "hot_key": hot_key,
        "reducer_input_count": len(bucket_items),
        "distinct_keys": len(by_user),
    }


def _map_chunk_job1b(args: tuple[list[tuple[tuple[str, str], tuple[int, int, float]]], bool]) -> dict[str, Any]:
    """Job 1b Map (+ Combiner opcional): emite o combina pares ((src, dst), (cnt, flags, views))."""
    chunk, use_combiner = args
    input_records = len(chunk)
    if use_combiner:
        agg: dict[tuple[str, str], list[float]] = {}
        for k, (c, f, v) in chunk:
            acc = agg.get(k)
            if acc is None:
                agg[k] = [c, f, v]
            else:
                acc[0] += c
                acc[1] += f
                acc[2] += v
        pairs = [(k, (int(v[0]), int(v[1]), float(v[2]))) for k, v in agg.items()]
    else:
        pairs = chunk
    shuffle_bytes = sum(len(k[0]) + len(k[1]) + 28 for k, _ in pairs)
    return {
        "input_records": input_records,
        "map_output_pairs": input_records,
        "shuffle_pairs": len(pairs),
        "shuffle_bytes": shuffle_bytes,
        "pairs": pairs,
    }


def _reduce_bucket_job1b(
    bucket_items: list[tuple[tuple[str, str], tuple[int, int, float]]]
) -> dict[str, Any]:
    """Job 1b Reduce: suma conteos, marcados y vistas por arista (src, dst)."""
    agg: dict[tuple[str, str], list[float]] = {}
    key_counts: dict[tuple[str, str], int] = defaultdict(int)
    for k, (c, f, v) in bucket_items:
        key_counts[k] += 1
        acc = agg.get(k)
        if acc is None:
            agg[k] = [c, f, v]
        else:
            acc[0] += c
            acc[1] += f
            acc[2] += v
    edges = {
        k: (int(v[0]), int(v[1]), float(v[2]))
        for k, v in agg.items()
    }
    return {
        "edges": edges,
        "reducer_input_count": len(bucket_items),
        "max_key_load": max(key_counts.values(), default=0),
    }


def _map_chunk_job2(args: tuple[list[dict[str, Any]], bool]) -> dict[str, Any]:
    """Job 2 Map (+ Combiner opcional): de aristas emite salidas y entradas por categoría."""
    edges_chunk, use_combiner = args
    raw_pairs: list[tuple[str, tuple[int, int, float, float]]] = []
    for e in edges_chunk:
        cnt = int(e["transition_count"])
        fl_sum = float(e["flagged_frac"]) * cnt
        vw_sum = float(e["avg_view_count_1h"]) * cnt
        # (out_count, in_count, in_flagged_sum, in_views_sum)
        raw_pairs.append((e["from_category"], (cnt, 0, 0.0, 0.0)))
        raw_pairs.append((e["to_category"], (0, cnt, fl_sum, vw_sum)))

    if use_combiner:
        agg: dict[str, list[float]] = {}
        for cat, (oc, ic, fs, vs) in raw_pairs:
            acc = agg.get(cat)
            if acc is None:
                agg[cat] = [oc, ic, fs, vs]
            else:
                acc[0] += oc
                acc[1] += ic
                acc[2] += fs
                acc[3] += vs
        pairs = [(cat, (int(v[0]), int(v[1]), float(v[2]), float(v[3]))) for cat, v in agg.items()]
    else:
        pairs = raw_pairs

    shuffle_bytes = sum(len(k) + 36 for k, _ in pairs)
    return {
        "input_records": len(edges_chunk),
        "map_output_pairs": len(raw_pairs),
        "shuffle_pairs": len(pairs),
        "shuffle_bytes": shuffle_bytes,
        "pairs": pairs,
    }


def _reduce_bucket_job2(
    bucket_items: list[tuple[str, tuple[int, int, float, float]]]
) -> dict[str, Any]:
    """Job 2 Reduce: construye el Node Summary por categoría."""
    agg: dict[str, list[float]] = {}
    key_counts: dict[str, int] = defaultdict(int)
    for cat, (oc, ic, fs, vs) in bucket_items:
        key_counts[cat] += 1
        acc = agg.get(cat)
        if acc is None:
            agg[cat] = [oc, ic, fs, vs]
        else:
            acc[0] += oc
            acc[1] += ic
            acc[2] += fs
            acc[3] += vs

    nodes = []
    for cat, (oc, ic, fs, vs) in agg.items():
        oc_i, ic_i = int(oc), int(ic)
        nodes.append({
            "category": cat,
            "out_transition_count": oc_i,
            "in_transition_count": ic_i,
            "net_flow": ic_i - oc_i,
            "flagged_frac": round(fs / ic_i, 4) if ic_i > 0 else 0.0,
            "avg_view_count_1h": round(vs / ic_i, 2) if ic_i > 0 else 0.0,
        })
    return {
        "nodes": nodes,
        "reducer_input_count": len(bucket_items),
        "max_key_load": max(key_counts.values(), default=0),
    }


def _map_chunk_s10_pagerank(args: tuple[list[tuple[str, str, float]], dict[str, float]]) -> dict[str, Any]:
    """S10 Map: para cada entrada p(i,j) de la matriz emite (j, p(i,j) * v_i)."""
    entries, v = args
    pairs = [(dst, prob * v[src]) for src, dst, prob in entries]
    shuffle_bytes = sum(len(dst) + 16 for dst, _ in pairs)
    return {
        "input_records": len(entries),
        "map_output_pairs": len(pairs),
        "shuffle_pairs": len(pairs),
        "shuffle_bytes": shuffle_bytes,
        "pairs": pairs,
    }


def _reduce_bucket_s10_pagerank(args: tuple[list[tuple[str, float]], float, int]) -> dict[str, Any]:
    """S10 Reduce: suma contribuciones entrantes por j y aplica damping."""
    bucket_items, damping, num_nodes = args
    sums: dict[str, float] = defaultdict(float)
    key_counts: dict[str, int] = defaultdict(int)
    for dst, contrib in bucket_items:
        sums[dst] += contrib
        key_counts[dst] += 1
    out = {dst: damping * total + (1.0 - damping) / num_nodes for dst, total in sums.items()}
    return {
        "scores": out,
        "reducer_input_count": len(bucket_items),
        "max_key_load": max(key_counts.values(), default=0),
    }


def _heavy_moderation_score(cat: str, flagged: int, views: float) -> float:
    """Cómputo CPU representativo de extracción de señales de riesgo por upload en moderación."""
    x = math.log1p(views) * (1.5 if flagged else 1.0)
    # 25 iteraciones ligeras para que el cómputo CPU domine sobre la serialización IPC en Windows
    for step in range(1, 26):
        x = math.sin(x + step * 0.13) * 0.5 + math.sqrt(abs(x) + 1.0)
    return x


def _map_chunk_s14_skew(
    args: tuple[list[tuple[str, int, float]], bool, bool, int, str]
) -> dict[str, Any]:
    """S14 Map: emite por categoría (sin mitigar) o con salting uniforme + combiner (mitigado)."""
    chunk, use_salting, use_combiner, num_salts, _hot_category = args
    input_records = len(chunk)
    raw_count = input_records

    if use_combiner:
        agg: dict[str, list[float]] = {}
        for idx, (cat, flagged, views) in enumerate(chunk):
            key = f"{cat}#s{idx % num_salts}" if use_salting else cat
            score = _heavy_moderation_score(cat, flagged, views)
            acc = agg.get(key)
            if acc is None:
                agg[key] = [1.0, float(flagged), views, score]
            else:
                acc[0] += 1.0
                acc[1] += flagged
                acc[2] += views
                acc[3] += score
        pairs = [(k, (int(v[0]), int(v[1]), float(v[2]), float(v[3]))) for k, v in agg.items()]
    else:
        pairs = []
        for idx, (cat, flagged, views) in enumerate(chunk):
            key = f"{cat}#s{idx % num_salts}" if use_salting else cat
            pairs.append((key, (1, flagged, views, 0.0)))

    shuffle_bytes = sum(len(k) + 32 for k, _ in pairs)
    return {
        "input_records": input_records,
        "map_output_pairs": raw_count,
        "shuffle_pairs": len(pairs),
        "shuffle_bytes": shuffle_bytes,
        "pairs": pairs,
    }


def _reduce_bucket_s14_skew(
    args: tuple[list[tuple[str, tuple[int, int, float, float]]], bool]
) -> dict[str, Any]:
    """S14 Reduce: agrega métricas de riesgo por clave (computa score si no vino pre-combinado)."""
    bucket_items, already_combined = args
    agg: dict[str, list[float]] = {}
    for key, (cnt, fl, vw, pre_score) in bucket_items:
        score = pre_score if already_combined else _heavy_moderation_score(key, fl, vw)
        acc = agg.get(key)
        if acc is None:
            agg[key] = [float(cnt), float(fl), vw, score]
        else:
            acc[0] += cnt
            acc[1] += fl
            acc[2] += vw
            acc[3] += score

    return {
        "agg": {k: (int(v[0]), int(v[1]), float(v[2]), float(v[3])) for k, v in agg.items()},
        "reducer_input_count": len(bucket_items),
    }


# --------------------------------------------------------------------------- #
# Runner genérico reutilizable (usado en W4 y también por W5 Task 4 MinHash/LSH)
# --------------------------------------------------------------------------- #
def _generic_map_worker(args: tuple[Callable, Any]) -> list[tuple[Any, Any]]:
    map_fn, fragment = args
    return map_fn(fragment)


def _generic_reduce_worker(args: tuple[Callable, list[tuple[Any, Any]]]) -> list[Any]:
    reduce_fn, items = args
    grouped: dict[Any, list[Any]] = defaultdict(list)
    for k, v in items:
        grouped[k].append(v)
    out = []
    for k, vals in grouped.items():
        res = reduce_fn(k, vals)
        if res is not None:
            if isinstance(res, list):
                out.extend(res)
            else:
                out.append(res)
    return out


class MapReduceRunner:
    """Runner MapReduce paralelo (ProcessPoolExecutor) con métricas de shuffle y reducers."""

    def __init__(self, num_workers: int = 4, num_reducers: int = 4):
        self.num_workers = max(1, int(num_workers))
        self.num_reducers = max(1, int(num_reducers))

    def run(
        self,
        fragments: list[Any],
        map_fn: Callable[[Any], list[tuple[Any, Any]]],
        reduce_fn: Callable[[Any, list[Any]], Any],
        combiner_fn: Callable[[list[tuple[Any, Any]]], list[tuple[Any, Any]]] | None = None,
    ) -> tuple[list[Any], dict[str, Any]]:
        t0 = time.perf_counter()
        if self.num_workers > 1 and len(fragments) > 1:
            with ProcessPoolExecutor(max_workers=self.num_workers) as ex:
                mapped_lists = list(ex.map(_generic_map_worker, [(map_fn, f) for f in fragments]))
        else:
            mapped_lists = [map_fn(f) for f in fragments]
        t_map = time.perf_counter()

        map_output_pairs = sum(len(lst) for lst in mapped_lists)
        if combiner_fn is not None:
            shuffled_lists = [combiner_fn(lst) for lst in mapped_lists]
        else:
            shuffled_lists = mapped_lists

        buckets: list[list[tuple[Any, Any]]] = [[] for _ in range(self.num_reducers)]
        shuffle_pairs = 0
        for lst in shuffled_lists:
            shuffle_pairs += len(lst)
            for k, v in lst:
                buckets[_stable_partition(k, self.num_reducers)].append((k, v))

        reducer_loads = [len(b) for b in buckets]
        non_empty_buckets = [b for b in buckets if b]

        t_red_start = time.perf_counter()
        if self.num_workers > 1 and len(non_empty_buckets) > 1:
            with ProcessPoolExecutor(max_workers=min(self.num_workers, len(non_empty_buckets))) as ex:
                reduced_lists = list(ex.map(_generic_reduce_worker, [(reduce_fn, b) for b in non_empty_buckets]))
        else:
            reduced_lists = [_generic_reduce_worker((reduce_fn, b)) for b in non_empty_buckets]
        t_end = time.perf_counter()

        outputs = [item for sub in reduced_lists for item in sub]
        mean_load = statistics.mean(reducer_loads) if reducer_loads else 0.0
        max_load = max(reducer_loads) if reducer_loads else 0
        metrics = {
            "num_fragments": len(fragments),
            "num_workers": self.num_workers,
            "num_reducers": self.num_reducers,
            "map_output_pairs": map_output_pairs,
            "shuffle_pairs": shuffle_pairs,
            "reducer_loads": reducer_loads,
            "max_reducer_load": max_load,
            "min_reducer_load": min(reducer_loads) if reducer_loads else 0,
            "mean_reducer_load": mean_load,
            "load_balance_factor": (max_load / mean_load) if mean_load > 0 else 1.0,
            "map_time_ms": (t_map - t0) * 1000.0,
            "reduce_time_ms": (t_end - t_red_start) * 1000.0,
            "wall_time_ms": (t_end - t0) * 1000.0,
        }
        return outputs, metrics


# --------------------------------------------------------------------------- #
# Generación de fragmentos y datos a gran escala (100,000+ uploads)
# --------------------------------------------------------------------------- #
def write_fragments_jsonl(
    records: list[dict[str, Any]],
    out_dir: Path = FRAGMENTS_W4_DIR,
    num_fragments: int = 8,
) -> list[Path]:
    """Divide los uploads en >=8 archivos fragmento JSONL para ejecución Map paralela."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Limpiar fragmentos antiguos
    for old in out_dir.glob("part_*.jsonl"):
        old.unlink()

    paths: list[Path] = []
    n = len(records)
    chunk_size = math.ceil(n / num_fragments)
    for i in range(num_fragments):
        part_path = out_dir / f"part_{i:02d}.jsonl"
        chunk = records[i * chunk_size:(i + 1) * chunk_size]
        with open(part_path, "w", encoding="utf-8") as fh:
            for row in chunk:
                fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
        paths.append(part_path)
    return paths


def generate_scaled_uploads(
    count: int = 100_000,
    num_uploaders: int = 5_000,
    seed: int = 42,
    hot_category: str | None = None,
    hot_share: float = 0.0,
) -> list[tuple[str, int, str, int, float]]:
    """Genera `count` uploads sintéticos compactos (uploader_id, seq, cat, flagged, views).

    Usa distribución Zipfiana suave sobre uploaders para producir una clave caliente realista
    (uploader más activo) y permite inyectar una ola de spam en `hot_category` (>=40%).
    """
    rng = np.random.default_rng(seed)
    cats = list(CATEGORIES)
    n_cats = len(cats)

    if hot_category and hot_share > 0.0:
        hot_idx = cats.index(hot_category)
        rem = (1.0 - hot_share) / (n_cats - 1)
        probs = np.full(n_cats, rem)
        probs[hot_idx] = hot_share
    else:
        probs = np.full(n_cats, 1.0 / n_cats)

    cat_indices = rng.choice(n_cats, size=count, p=probs)
    flag_probs = np.array([FLAG_PROBABILITY[c] for c in cats])[cat_indices]
    if hot_category and hot_share > 0.0:
        # La ola de spam eleva la tasa de marcados en la categoría afectada
        hot_idx = cats.index(hot_category)
        flag_probs = np.where(cat_indices == hot_idx, 0.28, flag_probs)

    flagged_arr = (rng.random(count) < flag_probs).astype(np.int8)
    views_arr = np.minimum(100_000.0, np.round(rng.lognormal(mean=7.3, sigma=0.75, size=count), 1))

    # Uploaders: ~85% uniformes + ~15% power-users (uno destacado como hot key realista)
    u_weights = np.ones(num_uploaders, dtype=np.float64)
    u_weights[0] = 35.0
    u_weights[1:25] = 8.0
    u_weights /= u_weights.sum()
    u_indices = rng.choice(num_uploaders, size=count, p=u_weights)

    return [
        (f"USER_{int(u_indices[i]):05d}", i + 1, cats[int(cat_indices[i])], int(flagged_arr[i]), float(views_arr[i]))
        for i in range(count)
    ]


# --------------------------------------------------------------------------- #
# Task 1: MapReduce Pipeline (Job 1 + Job 2) y validación contra Unidad 3
# --------------------------------------------------------------------------- #
def run_job1_from_fragments(
    fragment_paths: list[Path],
    num_workers: int = 4,
    num_reducers: int = 4,
    use_combiner: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ejecuta Job 1 (Stage 1a secuenciación por uploader + Stage 1b suma de aristas)."""
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=num_workers) as ex:
        # Warmup
        list(ex.map(_noop_warmup, range(num_workers)))
        t_start = time.perf_counter()

        # --- Stage 1a: Map sobre >=8 archivos fragmento ---
        map1a_res = list(ex.map(_map_file_job1a, [(str(p), False) for p in fragment_paths]))

        buckets_1a: list[list[tuple[str, tuple[int, str, int, float]]]] = [[] for _ in range(num_reducers)]
        for r in map1a_res:
            for k, v in r["pairs"]:
                buckets_1a[_stable_partition(k, num_reducers)].append((k, v))

        red1a_res = list(ex.map(_reduce_bucket_job1a, buckets_1a))

        # Recolectar eventos de arista para Stage 1b divididos en len(fragment_paths) chunks
        all_edge_events: list[tuple[tuple[str, str], tuple[int, int, float]]] = []
        for rr in red1a_res:
            all_edge_events.extend(rr["edge_events"])

        n_chunks = len(fragment_paths)
        chunk_sz = max(1, math.ceil(len(all_edge_events) / n_chunks))
        chunks_1b = [
            all_edge_events[i * chunk_sz:(i + 1) * chunk_sz]
            for i in range(n_chunks)
            if i * chunk_sz < len(all_edge_events)
        ]

        # --- Stage 1b: Map (+ Combiner opcional) y Reduce de aristas ---
        map1b_res = list(ex.map(_map_chunk_job1b, [(ch, use_combiner) for ch in chunks_1b]))

        buckets_1b: list[list[tuple[tuple[str, str], tuple[int, int, float]]]] = [[] for _ in range(num_reducers)]
        for r in map1b_res:
            for k, v in r["pairs"]:
                buckets_1b[_stable_partition(k, num_reducers)].append((k, v))

        red1b_res = list(ex.map(_reduce_bucket_job1b, buckets_1b))
        t_end = time.perf_counter()

    # Consolidar aristas finales ordenadas
    merged_edges: dict[tuple[str, str], tuple[int, int, float]] = {}
    for rr in red1b_res:
        merged_edges.update(rr["edges"])

    edges_out = []
    for idx, ((src, dst), (cnt, fl, vw)) in enumerate(sorted(merged_edges.items()), start=1):
        edges_out.append({
            "edge_id": f"e{idx:03d}",
            "from_category": src,
            "to_category": dst,
            "transition_count": cnt,
            "flagged_frac": round(fl / cnt, 4) if cnt else 0.0,
            "avg_view_count_1h": round(vw / cnt, 2) if cnt else 0.0,
        })

    # Métricas detalladas Stage 1a y Stage 1b
    in_1a = sum(r["input_records"] for r in map1a_res)
    shuf_pairs_1a = sum(r["shuffle_pairs"] for r in map1a_res)
    shuf_bytes_1a = sum(r["shuffle_bytes"] for r in map1a_res)
    loads_1a = [rr["reducer_input_count"] for rr in red1a_res]
    hot_rec = max(red1a_res, key=lambda x: x["max_key_load"])

    in_1b = sum(r["input_records"] for r in map1b_res)
    map_out_1b = sum(r["map_output_pairs"] for r in map1b_res)
    shuf_pairs_1b = sum(r["shuffle_pairs"] for r in map1b_res)
    shuf_bytes_1b = sum(r["shuffle_bytes"] for r in map1b_res)
    loads_1b = [rr["reducer_input_count"] for rr in red1b_res]

    metrics = {
        "num_fragments": len(fragment_paths),
        "num_workers": num_workers,
        "num_reducers": num_reducers,
        "use_combiner": use_combiner,
        "input_uploads": in_1a,
        "output_edges": len(edges_out),
        "total_transitions": sum(e["transition_count"] for e in edges_out),
        "wall_time_ms": (t_end - t_start) * 1000.0,
        "total_with_pool_ms": (t_end - t0) * 1000.0,
        "stage_1a": {
            "input_records": in_1a,
            "shuffle_pairs": shuf_pairs_1a,
            "shuffle_bytes": shuf_bytes_1a,
            "replication_rate_r": shuf_pairs_1a / in_1a if in_1a else 0.0,
            "reducer_loads": loads_1a,
            "max_reducer_load_q": max(loads_1a) if loads_1a else 0,
            "mean_reducer_load": statistics.mean(loads_1a) if loads_1a else 0.0,
            "load_balance_factor": (max(loads_1a) / statistics.mean(loads_1a)) if loads_1a and statistics.mean(loads_1a) > 0 else 1.0,
            "hot_key_uploader": hot_rec["hot_key"],
            "hot_key_uploads_q": hot_rec["max_key_load"],
        },
        "stage_1b": {
            "input_records": in_1b,
            "map_output_pairs": map_out_1b,
            "shuffle_pairs": shuf_pairs_1b,
            "shuffle_bytes": shuf_bytes_1b,
            "replication_rate_r": shuf_pairs_1b / in_1b if in_1b else 0.0,
            "reducer_loads": loads_1b,
            "max_reducer_load_q": max(loads_1b) if loads_1b else 0,
            "mean_reducer_load": statistics.mean(loads_1b) if loads_1b else 0.0,
            "load_balance_factor": (max(loads_1b) / statistics.mean(loads_1b)) if loads_1b and statistics.mean(loads_1b) > 0 else 1.0,
        },
        "total_shuffle_pairs": shuf_pairs_1a + shuf_pairs_1b,
        "total_shuffle_bytes": shuf_bytes_1a + shuf_bytes_1b,
    }
    return edges_out, metrics


def run_job2_node_summary(
    edges: list[dict[str, Any]],
    num_workers: int = 4,
    num_reducers: int = 4,
    use_combiner: bool = True,
    num_fragments: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Job 2: construye el resumen de nodos (Node Summary) a partir de las aristas."""
    chunk_sz = max(1, math.ceil(len(edges) / num_fragments))
    chunks = [edges[i * chunk_sz:(i + 1) * chunk_sz] for i in range(num_fragments) if i * chunk_sz < len(edges)]

    with ProcessPoolExecutor(max_workers=num_workers) as ex:
        list(ex.map(_noop_warmup, range(num_workers)))
        t_start = time.perf_counter()

        map_res = list(ex.map(_map_chunk_job2, [(ch, use_combiner) for ch in chunks]))
        buckets: list[list[tuple[str, tuple[int, int, float, float]]]] = [[] for _ in range(num_reducers)]
        for r in map_res:
            for k, v in r["pairs"]:
                buckets[_stable_partition(k, num_reducers)].append((k, v))

        red_res = list(ex.map(_reduce_bucket_job2, buckets))
        t_end = time.perf_counter()

    nodes = [node for rr in red_res for node in rr["nodes"]]
    nodes.sort(key=lambda x: x["category"])

    in_recs = sum(r["input_records"] for r in map_res)
    map_out = sum(r["map_output_pairs"] for r in map_res)
    shuf_pairs = sum(r["shuffle_pairs"] for r in map_res)
    shuf_bytes = sum(r["shuffle_bytes"] for r in map_res)
    loads = [rr["reducer_input_count"] for rr in red_res]
    mean_load = statistics.mean(loads) if loads else 0.0

    metrics = {
        "input_edges": in_recs,
        "map_output_pairs": map_out,
        "shuffle_pairs": shuf_pairs,
        "shuffle_bytes": shuf_bytes,
        "replication_rate_r": map_out / in_recs if in_recs else 0.0,
        "effective_r_with_combiner": shuf_pairs / in_recs if in_recs else 0.0,
        "reducer_loads": loads,
        "max_reducer_load_q": max(loads) if loads else 0,
        "mean_reducer_load": mean_load,
        "load_balance_factor": (max(loads) / mean_load) if mean_load > 0 else 1.0,
        "net_flow_sum_check": sum(n["net_flow"] for n in nodes),
        "wall_time_ms": (t_end - t_start) * 1000.0,
    }
    return nodes, metrics


def validate_against_unit3(mr_edges: list[dict[str, Any]], unit3_edges_df: pd.DataFrame) -> dict[str, Any]:
    """Valida arista por arista que Job 1 reproduce exactamente Unidad 3."""
    mr_map = {(e["from_category"], e["to_category"]): e for e in mr_edges}
    u3_map = {
        (row["from_category"], row["to_category"]): row
        for row in unit3_edges_df.to_dict("records")
    }
    all_keys = sorted(set(mr_map) | set(u3_map))
    count_diffs = 0
    max_flag_diff = 0.0
    max_view_diff = 0.0
    for k in all_keys:
        a = mr_map.get(k)
        b = u3_map.get(k)
        if a is None or b is None:
            count_diffs += 1
            continue
        if int(a["transition_count"]) != int(b["transition_count"]):
            count_diffs += 1
        max_flag_diff = max(max_flag_diff, abs(float(a["flagged_frac"]) - float(b["flagged_frac"])))
        max_view_diff = max(max_view_diff, abs(float(a["avg_view_count_1h"]) - float(b["avg_view_count_1h"])))

    return {
        "edges_checked": len(all_keys),
        "mr_edges_count": len(mr_edges),
        "unit3_edges_count": len(u3_map),
        "transition_count_mismatches": count_diffs,
        "max_flagged_frac_diff": max_flag_diff,
        "max_avg_view_diff": max_view_diff,
        "passed": count_diffs == 0 and max_flag_diff < 1e-4 and max_view_diff < 0.02,
    }


# --------------------------------------------------------------------------- #
# Task 2 (S10): PageRank iterativo por multiplicación matriz-vector en MapReduce
# --------------------------------------------------------------------------- #
def run_s10_pagerank_mr(
    edges: list[dict[str, Any]],
    unit3_pagerank: dict[str, float],
    damping: float = 0.85,
    tol: float = 1e-10,
    max_iter: int = 100,
    num_workers: int = 4,
    num_reducers: int = 4,
) -> dict[str, Any]:
    """Itera v^(t+1) = d * P^T v^(t) + (1-d)/N usando Map(j, p(i,j)*v_i) + Reduce(sum)."""
    out_totals: dict[str, int] = defaultdict(int)
    cats_set: set[str] = set()
    for e in edges:
        out_totals[e["from_category"]] += int(e["transition_count"])
        cats_set.add(e["from_category"])
        cats_set.add(e["to_category"])
    cats = sorted(cats_set)
    n = len(cats)

    # Entradas dispersas de la matriz estocástica P: (i, j, p(i,j))
    matrix_entries: list[tuple[str, str, float]] = [
        (e["from_category"], e["to_category"], int(e["transition_count"]) / out_totals[e["from_category"]])
        for e in edges
        if out_totals[e["from_category"]] > 0
    ]
    chunk_sz = max(1, math.ceil(len(matrix_entries) / num_workers))
    entry_chunks = [
        matrix_entries[i * chunk_sz:(i + 1) * chunk_sz]
        for i in range(num_workers)
        if i * chunk_sz < len(matrix_entries)
    ]

    v = {c: 1.0 / n for c in cats}
    total_pairs = 0
    total_bytes = 0
    pairs_per_iter = len(matrix_entries)
    last_reducer_loads: list[int] = []
    max_key_in_degree = 0
    history = []

    with ProcessPoolExecutor(max_workers=num_workers) as ex:
        list(ex.map(_noop_warmup, range(num_workers)))
        t_start = time.perf_counter()
        iters = 0
        for it in range(1, max_iter + 1):
            iters = it
            map_res = list(ex.map(_map_chunk_s10_pagerank, [(ch, v) for ch in entry_chunks]))
            buckets: list[list[tuple[str, float]]] = [[] for _ in range(num_reducers)]
            for r in map_res:
                total_pairs += r["shuffle_pairs"]
                total_bytes += r["shuffle_bytes"]
                for dst, val in r["pairs"]:
                    buckets[_stable_partition(dst, num_reducers)].append((dst, val))

            red_res = list(ex.map(_reduce_bucket_s10_pagerank, [(b, damping, n) for b in buckets]))
            last_reducer_loads = [rr["reducer_input_count"] for rr in red_res]
            max_key_in_degree = max(rr["max_key_load"] for rr in red_res)

            v_new = {c: (1.0 - damping) / n for c in cats}
            for rr in red_res:
                v_new.update(rr["scores"])
            s = sum(v_new.values())
            v_new = {c: val / s for c, val in v_new.items()}

            l1_diff = sum(abs(v_new[c] - v[c]) for c in cats)
            history.append({"iteration": it, "l1_residual": l1_diff})
            v = v_new
            if l1_diff < tol:
                break
        t_end = time.perf_counter()

    comparison = []
    max_abs_diff = 0.0
    for c in cats:
        u3_val = float(unit3_pagerank.get(c, 0.0))
        diff = abs(v[c] - u3_val)
        max_abs_diff = max(max_abs_diff, diff)
        comparison.append({
            "category": c,
            "mr_pagerank": v[c],
            "unit3_pagerank": u3_val,
            "abs_diff": diff,
        })
    comparison.sort(key=lambda x: x["mr_pagerank"], reverse=True)

    return {
        "damping": damping,
        "tolerance": tol,
        "iterations": iters,
        "pairs_per_iteration": pairs_per_iter,
        "total_s10_pairs": total_pairs,
        "total_s10_shuffle_bytes": total_bytes,
        "replication_rate_r": pairs_per_iter / len(matrix_entries) if matrix_entries else 0.0,
        "max_reducer_load_q": max(last_reducer_loads) if last_reducer_loads else 0,
        "max_key_in_degree": max_key_in_degree,
        "max_abs_diff_vs_unit3": max_abs_diff,
        "within_1e4": max_abs_diff < 1e-4,
        "wall_time_ms": (t_end - t_start) * 1000.0,
        "comparison": comparison,
        "convergence_history": history[:20],
    }


# --------------------------------------------------------------------------- #
# Task 3: Análisis de Costos (Combiner + Escalamiento 1x, 2x, 4x -> 10x + S10)
# --------------------------------------------------------------------------- #
def _run_edge_pipeline_in_memory(
    uploads: list[tuple[str, int, str, int, float]],
    num_fragments: int = 8,
    use_combiner: bool = False,
) -> dict[str, Any]:
    """Ejecuta el pipeline completo Job 1a + Job 1b + Job 2 midiendo pares y bytes de shuffle."""
    t0 = time.perf_counter()
    n = len(uploads)
    chunk_sz = math.ceil(n / num_fragments)

    # Job 1a: Map emite (uploader_id, (seq, cat, flagged, views)) -> shuffle exacto = n pares
    shuf_pairs_1a = n
    shuf_bytes_1a = sum(len(u) + len(cat) + 32 for u, _, cat, _, _ in uploads)

    # Reduce 1a: ordenar por stream_seq y emitir pares consecutivos por uploader
    by_user: dict[str, list[tuple[int, str, int, float]]] = defaultdict(list)
    for u, seq, cat, fl, vw in uploads:
        by_user[u].append((seq, cat, fl, vw))

    # Dividir eventos de transición en num_fragments mappers para Job 1b
    edge_events: list[tuple[tuple[str, str], tuple[int, int, float]]] = []
    for seq_vals in by_user.values():
        if len(seq_vals) < 2:
            continue
        seq_vals.sort(key=lambda x: x[0])
        for i in range(len(seq_vals) - 1):
            edge_events.append(((seq_vals[i][1], seq_vals[i + 1][1]), (1, seq_vals[i + 1][2], seq_vals[i + 1][3])))

    m_events = len(edge_events)
    ev_chunk_sz = max(1, math.ceil(m_events / num_fragments))

    shuf_pairs_1b = 0
    shuf_bytes_1b = 0
    final_edges: dict[tuple[str, str], list[float]] = {}
    for i in range(num_fragments):
        ch = edge_events[i * ev_chunk_sz:(i + 1) * ev_chunk_sz]
        if not ch:
            continue
        if use_combiner:
            local_agg: dict[tuple[str, str], list[float]] = {}
            for k, (c, f, v) in ch:
                acc = local_agg.get(k)
                if acc is None:
                    local_agg[k] = [c, f, v]
                else:
                    acc[0] += c
                    acc[1] += f
                    acc[2] += v
            shuf_pairs_1b += len(local_agg)
            shuf_bytes_1b += sum(len(k[0]) + len(k[1]) + 28 for k in local_agg)
            for k, acc in local_agg.items():
                g = final_edges.get(k)
                if g is None:
                    final_edges[k] = list(acc)
                else:
                    g[0] += acc[0]
                    g[1] += acc[1]
                    g[2] += acc[2]
        else:
            shuf_pairs_1b += len(ch)
            shuf_bytes_1b += sum(len(k[0]) + len(k[1]) + 28 for k, _ in ch)
            for k, (c, f, v) in ch:
                g = final_edges.get(k)
                if g is None:
                    final_edges[k] = [c, f, v]
                else:
                    g[0] += c
                    g[1] += f
                    g[2] += v

    # Job 2: desde aristas a resumen de nodos
    edge_items = list(final_edges.items())
    e_chunk_sz = max(1, math.ceil(len(edge_items) / num_fragments))
    shuf_pairs_2 = 0
    shuf_bytes_2 = 0
    for i in range(num_fragments):
        ch = edge_items[i * e_chunk_sz:(i + 1) * e_chunk_sz]
        if not ch:
            continue
        if use_combiner:
            cats_seen = {src for (src, _), _ in ch} | {dst for (_, dst), _ in ch}
            shuf_pairs_2 += len(cats_seen)
            shuf_bytes_2 += sum(len(c) + 36 for c in cats_seen)
        else:
            shuf_pairs_2 += 2 * len(ch)
            shuf_bytes_2 += sum(len(src) + len(dst) + 72 for (src, dst), _ in ch)

    wall_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "uploads": n,
        "transitions": m_events,
        "shuffle_pairs_job1a": shuf_pairs_1a,
        "shuffle_pairs_job1b": shuf_pairs_1b,
        "shuffle_pairs_job2": shuf_pairs_2,
        "shuffle_pairs_total": shuf_pairs_1a + shuf_pairs_1b + shuf_pairs_2,
        "shuffle_bytes_job1a": shuf_bytes_1a,
        "shuffle_bytes_job1b": shuf_bytes_1b,
        "shuffle_bytes_job2": shuf_bytes_2,
        "shuffle_bytes_total": shuf_bytes_1a + shuf_bytes_1b + shuf_bytes_2,
        "wall_time_ms": wall_ms,
    }


def run_cost_analysis(s10_result: dict[str, Any], base_count: int = 100_000) -> dict[str, Any]:
    """Task 3: Shuffle con/sin combiner a 1x, 2x, 4x, chequeo lineal y extrapolación a 10x + S10."""
    scales = (1, 2, 4)
    rows = []
    for factor in scales:
        n = base_count * factor
        uploads = generate_scaled_uploads(count=n, num_uploaders=5_000 * factor, seed=42 + factor)
        no_comb = _run_edge_pipeline_in_memory(uploads, num_fragments=8, use_combiner=False)
        with_comb = _run_edge_pipeline_in_memory(uploads, num_fragments=8, use_combiner=True)

        # Reducción de shuffle en Job 1b + Job 2 (las etapas donde aplica combiner asociativo)
        agg_no = no_comb["shuffle_pairs_job1b"] + no_comb["shuffle_pairs_job2"]
        agg_yes = with_comb["shuffle_pairs_job1b"] + with_comb["shuffle_pairs_job2"]
        agg_reduction = (1.0 - agg_yes / agg_no) if agg_no > 0 else 0.0

        total_reduction_pairs = 1.0 - (with_comb["shuffle_pairs_total"] / no_comb["shuffle_pairs_total"])
        total_reduction_bytes = 1.0 - (with_comb["shuffle_bytes_total"] / no_comb["shuffle_bytes_total"])

        rows.append({
            "scale": f"{factor}x",
            "factor": factor,
            "uploads": n,
            "transitions": no_comb["transitions"],
            "no_combiner_pairs": no_comb["shuffle_pairs_total"],
            "with_combiner_pairs": with_comb["shuffle_pairs_total"],
            "no_combiner_bytes": no_comb["shuffle_bytes_total"],
            "with_combiner_bytes": with_comb["shuffle_bytes_total"],
            "job1b_no_combiner_pairs": no_comb["shuffle_pairs_job1b"],
            "job1b_with_combiner_pairs": with_comb["shuffle_pairs_job1b"],
            "job1b_reduction_pct": agg_reduction * 100.0,
            "total_pairs_reduction_pct": total_reduction_pairs * 100.0,
            "total_bytes_reduction_pct": total_reduction_bytes * 100.0,
            "no_combiner_time_ms": no_comb["wall_time_ms"],
            "with_combiner_time_ms": with_comb["wall_time_ms"],
            "extrapolated": False,
        })

    # Regresión lineal sobre (uploads -> shuffle_pairs y bytes) y verificación R^2
    xs = np.array([r["uploads"] for r in rows], dtype=float)
    y_no = np.array([r["no_combiner_pairs"] for r in rows], dtype=float)
    y_yes = np.array([r["with_combiner_pairs"] for r in rows], dtype=float)
    b_no = np.array([r["no_combiner_bytes"] for r in rows], dtype=float)
    b_yes = np.array([r["with_combiner_bytes"] for r in rows], dtype=float)
    t_no = np.array([r["no_combiner_time_ms"] for r in rows], dtype=float)
    t_yes = np.array([r["with_combiner_time_ms"] for r in rows], dtype=float)

    def _fit_and_extrap(y: np.ndarray, x_target: float) -> tuple[float, float, float]:
        slope, intercept = np.polyfit(xs, y, 1)
        y_hat = slope * xs + intercept
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
        return float(slope * x_target + intercept), float(slope), r2

    target_10x = float(base_count * 10)
    p10_no, slope_no, r2_no = _fit_and_extrap(y_no, target_10x)
    p10_yes, slope_yes, r2_yes = _fit_and_extrap(y_yes, target_10x)
    b10_no, _, _ = _fit_and_extrap(b_no, target_10x)
    b10_yes, _, _ = _fit_and_extrap(b_yes, target_10x)
    t10_no, _, r2_time = _fit_and_extrap(t_no, target_10x)
    t10_yes, _, _ = _fit_and_extrap(t_yes, target_10x)

    extrap_row = {
        "scale": "10x (extrap.)",
        "factor": 10,
        "uploads": int(target_10x),
        "transitions": int(rows[0]["transitions"] * 10),
        "no_combiner_pairs": int(round(p10_no)),
        "with_combiner_pairs": int(round(p10_yes)),
        "no_combiner_bytes": int(round(b10_no)),
        "with_combiner_bytes": int(round(b10_yes)),
        "job1b_no_combiner_pairs": int(rows[0]["job1b_no_combiner_pairs"] * 10),
        "job1b_with_combiner_pairs": rows[0]["job1b_with_combiner_pairs"],  # acotado por M*|C|^2 = 800
        "job1b_reduction_pct": (1.0 - rows[0]["job1b_with_combiner_pairs"] / (rows[0]["job1b_no_combiner_pairs"] * 10)) * 100.0,
        "total_pairs_reduction_pct": (1.0 - p10_yes / p10_no) * 100.0,
        "total_bytes_reduction_pct": (1.0 - b10_yes / b10_no) * 100.0,
        "no_combiner_time_ms": t10_no,
        "with_combiner_time_ms": t10_yes,
        "extrapolated": True,
    }

    s10_cost = {
        "pairs_per_iteration": s10_result["pairs_per_iteration"],
        "iterations": s10_result["iterations"],
        "total_pairs": s10_result["total_s10_pairs"],
        "total_shuffle_bytes": s10_result["total_s10_shuffle_bytes"],
        "formula": f"{s10_result['pairs_per_iteration']} pairs/iter × {s10_result['iterations']} iters = {s10_result['total_s10_pairs']:,} pairs",
    }

    return {
        "base_count": base_count,
        "scaling_rows": rows + [extrap_row],
        "linearity": {
            "r2_no_combiner_pairs": r2_no,
            "r2_with_combiner_pairs": r2_yes,
            "r2_runtime": r2_time,
            "ratio_2x_to_1x_no_combiner": rows[1]["no_combiner_pairs"] / rows[0]["no_combiner_pairs"],
            "ratio_4x_to_1x_no_combiner": rows[2]["no_combiner_pairs"] / rows[0]["no_combiner_pairs"],
            "slope_pairs_per_upload_no_combiner": slope_no,
            "slope_pairs_per_upload_with_combiner": slope_yes,
            "is_linear": r2_no > 0.999 and r2_yes > 0.999,
        },
        "s10_cost": s10_cost,
        "combined_1x_total_pairs_with_combiner": rows[0]["with_combiner_pairs"] + s10_cost["total_pairs"],
        "combined_1x_total_pairs_no_combiner": rows[0]["no_combiner_pairs"] + s10_cost["total_pairs"],
    }


# --------------------------------------------------------------------------- #
# Task 4: Reducer Size (q) & Replication Rate (r) + Job 1 con R = 1, 2, 4, 8
# --------------------------------------------------------------------------- #
def run_reducer_size_analysis(
    fragment_paths_100k: list[Path],
    job1_metrics: dict[str, Any],
    job2_metrics: dict[str, Any],
    s10_result: dict[str, Any],
) -> dict[str, Any]:
    """Task 4: reporta r y q por job y ejecuta Job 1 con R = 1, 2, 4, 8 reduce tasks."""
    r_sweep = []
    for r_tasks in (1, 2, 4, 8):
        _, m = run_job1_from_fragments(
            fragment_paths_100k,
            num_workers=4,
            num_reducers=r_tasks,
            use_combiner=True,
        )
        s1a = m["stage_1a"]
        r_sweep.append({
            "R": r_tasks,
            "max_reducer_load": s1a["max_reducer_load_q"],
            "min_reducer_load": min(s1a["reducer_loads"]),
            "mean_reducer_load": s1a["mean_reducer_load"],
            "load_balance_factor": s1a["load_balance_factor"],
            "reducer_loads": s1a["reducer_loads"],
            "hot_key_uploader": s1a["hot_key_uploader"],
            "hot_key_q": s1a["hot_key_uploads_q"],
            "wall_time_ms": m["wall_time_ms"],
        })

    jobs_summary = [
        {
            "job": "Job 1a · Secuenciación por Uploader",
            "key": "uploader_id",
            "input_records": job1_metrics["stage_1a"]["input_records"],
            "replication_rate_r": job1_metrics["stage_1a"]["replication_rate_r"],
            "max_reducer_size_q": job1_metrics["stage_1a"]["max_reducer_load_q"],
            "hot_key": job1_metrics["stage_1a"]["hot_key_uploader"],
            "hot_key_count": job1_metrics["stage_1a"]["hot_key_uploads_q"],
            "notes": "Cada upload se emite exactamente 1 vez (r=1.0); la clave caliente acota inferiormente q.",
        },
        {
            "job": "Job 1b · Agregación de Aristas (con Combiner)",
            "key": "(from_category, to_category)",
            "input_records": job1_metrics["stage_1b"]["input_records"],
            "replication_rate_r": job1_metrics["stage_1b"]["replication_rate_r"],
            "max_reducer_size_q": job1_metrics["stage_1b"]["max_reducer_load_q"],
            "hot_key": "100 aristas combinadas",
            "hot_key_count": 8,
            "notes": "Combiner colapsa ~95k transiciones a <= 800 parciales (M × |C|²).",
        },
        {
            "job": "Job 2 · Resumen de Nodos (Node Summary)",
            "key": "category",
            "input_records": job2_metrics["input_edges"],
            "replication_rate_r": job2_metrics["replication_rate_r"],
            "max_reducer_size_q": job2_metrics["max_reducer_load_q"],
            "hot_key": "category (out + in)",
            "hot_key_count": 20,
            "notes": "Cada arista emite 2 pares (origen out y destino in → r=2.0 antes de combiner).",
        },
        {
            "job": "S10 · PageRank MapReduce (por iteración)",
            "key": "to_category (j)",
            "input_records": s10_result["pairs_per_iteration"],
            "replication_rate_r": s10_result["replication_rate_r"],
            "max_reducer_size_q": s10_result["max_reducer_load_q"],
            "hot_key": "to_category (grado entrada = 10)",
            "hot_key_count": s10_result["max_key_in_degree"],
            "notes": f"{s10_result['iterations']} iteraciones totales; cada entrada p(i,j) emite 1 par.",
        },
    ]

    return {
        "hot_key_uploader": job1_metrics["stage_1a"]["hot_key_uploader"],
        "hot_key_upload_count": job1_metrics["stage_1a"]["hot_key_uploads_q"],
        "jobs_rq": jobs_summary,
        "reducer_sweep": r_sweep,
    }


# --------------------------------------------------------------------------- #
# Task 5 (S14): Skewed Hot Key (>=40% spam wave) + Mitigation (Salting + Combiner)
# --------------------------------------------------------------------------- #
def run_s14_skew_and_mitigation(
    count: int = 120_000,
    hot_category: str = "Noticias",
    hot_share: float = 0.45,
    seed: int = 42,
) -> dict[str, Any]:
    """Inyecta ola de spam (>=40% en una categoría), mide P=1,2,4,8 antes y después de mitigar."""
    uploads_raw = generate_scaled_uploads(
        count=count,
        num_uploaders=5_000,
        seed=seed + 100,
        hot_category=hot_category,
        hot_share=hot_share,
    )
    # Tuplas compactas (category, is_flagged, view_count_1h)
    records = [(cat, fl, vw) for _, _, cat, fl, vw in uploads_raw]
    actual_hot_count = sum(1 for cat, _, _ in records if cat == hot_category)
    actual_hot_share = actual_hot_count / len(records)

    num_fragments = 8
    chunk_sz = math.ceil(len(records) / num_fragments)
    chunks = [records[i * chunk_sz:(i + 1) * chunk_sz] for i in range(num_fragments)]

    def _run_mode(p_workers: int, use_salting: bool, use_combiner: bool) -> dict[str, Any]:
        # Medir con pool ya calentado (como TaskTrackers persistentes de un cluster MapReduce)
        with ProcessPoolExecutor(max_workers=p_workers) as ex:
            list(ex.map(_noop_warmup, range(p_workers)))
            best_ms = float("inf")
            best_meta: dict[str, Any] = {}
            for _ in range(2):
                t0 = time.perf_counter()
                map_args = [(ch, use_salting, use_combiner, p_workers, hot_category) for ch in chunks]
                map_res = list(ex.map(_map_chunk_s14_skew, map_args))

                buckets: list[list[tuple[str, tuple[int, int, float, float]]]] = [[] for _ in range(p_workers)]
                shuffle_pairs = 0
                shuffle_bytes = 0
                for r in map_res:
                    shuffle_pairs += r["shuffle_pairs"]
                    shuffle_bytes += r["shuffle_bytes"]
                    for k, v in r["pairs"]:
                        if use_salting and "#s" in k:
                            salt_id = int(k.rsplit("#s", 1)[1]) % p_workers
                            buckets[salt_id].append((k, v))
                        else:
                            buckets[_stable_partition(k, p_workers)].append((k, v))

                red_args = [(b, use_combiner) for b in buckets]
                red_res = list(ex.map(_reduce_bucket_s14_skew, red_args))

                # Stage 2 merge trivial si se usó salting (a lo sumo |C|*P claves)
                final_cats: dict[str, list[float]] = {}
                for rr in red_res:
                    for k, (c, f, v, sc) in rr["agg"].items():
                        base_cat = k.split("#s", 1)[0]
                        acc = final_cats.get(base_cat)
                        if acc is None:
                            final_cats[base_cat] = [c, f, v, sc]
                        else:
                            acc[0] += c
                            acc[1] += f
                            acc[2] += v
                            acc[3] += sc

                wall_ms = (time.perf_counter() - t0) * 1000.0
                if wall_ms < best_ms:
                    best_ms = wall_ms
                    loads = [rr["reducer_input_count"] for rr in red_res]
                    mean_l = statistics.mean(loads) if loads else 0.0
                    max_l = max(loads) if loads else 0
                    # Para load balance real de trabajo (registros procesados por reducer antes de combiner):
                    raw_work_loads = [
                        sum(item[1][0] for item in b)
                        for b in buckets
                    ]
                    mean_w = statistics.mean(raw_work_loads) if raw_work_loads else 0.0
                    max_w = max(raw_work_loads) if raw_work_loads else 0
                    best_meta = {
                        "wall_time_ms": wall_ms,
                        "shuffle_pairs": shuffle_pairs,
                        "shuffle_bytes": shuffle_bytes,
                        "reducer_loads": loads,
                        "max_reducer_load": max_l,
                        "load_balance_factor": (max_l / mean_l) if mean_l > 0 else 1.0,
                        "effective_work_balance_factor": (max_w / mean_w) if mean_w > 0 else 1.0,
                        "categories_verified": len(final_cats),
                    }
        return best_meta

    workers_list = (1, 2, 4, 8)
    skewed_runs = {}
    mitigated_runs = {}
    for p in workers_list:
        skewed_runs[p] = _run_mode(p, use_salting=False, use_combiner=False)
        mitigated_runs[p] = _run_mode(p, use_salting=True, use_combiner=True)

    # Speedup y eficiencia: comparamos contra T_skewed(1) y T_mitigated(1)
    t1_skew = skewed_runs[1]["wall_time_ms"]
    t1_mit = mitigated_runs[1]["wall_time_ms"]

    rows = []
    for p in workers_list:
        sk = skewed_runs[p]
        mt = mitigated_runs[p]
        sp_sk = t1_skew / sk["wall_time_ms"] if sk["wall_time_ms"] > 0 else 1.0
        eff_sk = sp_sk / p
        sp_mt = t1_mit / mt["wall_time_ms"] if mt["wall_time_ms"] > 0 else 1.0
        eff_mt = sp_mt / p
        # Speedup absoluto de la solución mitigada respecto a la línea base secuencial sin mitigar
        abs_speedup_mt = t1_skew / mt["wall_time_ms"] if mt["wall_time_ms"] > 0 else 1.0

        rows.append({
            "P": p,
            "skewed_time_ms": sk["wall_time_ms"],
            "skewed_speedup": sp_sk,
            "skewed_efficiency": eff_sk,
            "skewed_load_balance": sk["load_balance_factor"],
            "skewed_max_reducer_load": sk["max_reducer_load"],
            "skewed_shuffle_pairs": sk["shuffle_pairs"],
            "mitigated_time_ms": mt["wall_time_ms"],
            "mitigated_speedup": sp_mt,
            "mitigated_efficiency": eff_mt,
            "mitigated_abs_speedup_vs_base": abs_speedup_mt,
            "mitigated_load_balance": mt["effective_work_balance_factor"],
            "mitigated_max_reducer_load": mt["max_reducer_load"],
            "mitigated_shuffle_pairs": mt["shuffle_pairs"],
            "ideal_speedup": float(p),
        })

    p8 = rows[-1]
    shuffle_reduction_pct = (1.0 - p8["mitigated_shuffle_pairs"] / p8["skewed_shuffle_pairs"]) * 100.0
    lbf_improvement_pct = (1.0 - p8["mitigated_load_balance"] / p8["skewed_load_balance"]) * 100.0
    time_speedup_at_p8 = p8["skewed_time_ms"] / p8["mitigated_time_ms"] if p8["mitigated_time_ms"] > 0 else 1.0

    return {
        "total_uploads": len(records),
        "hot_category": hot_category,
        "hot_category_count": actual_hot_count,
        "hot_category_share": actual_hot_share,
        "mitigation_strategy": "Salting de clave caliente (P cubetas) + Combiner local en Map + Merge final",
        "rows": rows,
        "summary_p8": {
            "skewed_load_balance": p8["skewed_load_balance"],
            "mitigated_load_balance": p8["mitigated_load_balance"],
            "lbf_reduction_pct": lbf_improvement_pct,
            "skewed_speedup": p8["skewed_speedup"],
            "mitigated_speedup": p8["mitigated_speedup"],
            "mitigated_abs_speedup_vs_base": p8["mitigated_abs_speedup_vs_base"],
            "skewed_efficiency": p8["skewed_efficiency"],
            "mitigated_efficiency": p8["mitigated_efficiency"],
            "time_improvement_factor_p8": time_speedup_at_p8,
            "shuffle_reduction_pct": shuffle_reduction_pct,
        },
    }


# --------------------------------------------------------------------------- #
# Orquestación completa del Workshop 4
# --------------------------------------------------------------------------- #
def run_workshop4(
    videos_w2_df: pd.DataFrame,
    edges_w3_df: pd.DataFrame,
    unit3_pagerank_map: dict[str, float],
) -> dict[str, Any]:
    """Ejecuta todas las tareas del Workshop 4, persiste JSONs y devuelve resultados."""
    # 1) Validación exacta sobre los 10 000 uploads de W2 divididos en 8 fragmentos JSONL
    w2_records = videos_w2_df.assign(
        upload_time=videos_w2_df["upload_time"].astype(str)
    ).to_dict("records")
    w2_frags_dir = FRAGMENTS_W4_DIR / "validation_w2"
    w2_frags = write_fragments_jsonl(w2_records, out_dir=w2_frags_dir, num_fragments=8)

    mr_edges_w2, job1_val_metrics = run_job1_from_fragments(
        w2_frags, num_workers=4, num_reducers=4, use_combiner=True
    )
    validation_u3 = validate_against_unit3(mr_edges_w2, edges_w3_df)

    # S10 PageRank MapReduce validado contra Unidad 3 (sobre las aristas de Unidad 3/W2)
    s10_val = run_s10_pagerank_mr(
        mr_edges_w2, unit3_pagerank_map, damping=0.85, tol=1e-10, num_workers=4, num_reducers=4
    )

    # 2) Pipeline principal a escala de 100,000 uploads divididos en 8 fragmentos JSONL en disco
    uploads_100k_tuples = generate_scaled_uploads(count=100_000, num_uploaders=5_000, seed=42)
    uploads_100k_dicts = [
        {
            "uploader_id": u,
            "stream_seq": seq,
            "category": cat,
            "is_flagged": bool(fl),
            "view_count_1h": vw,
        }
        for u, seq, cat, fl, vw in uploads_100k_tuples
    ]
    frags_100k = write_fragments_jsonl(uploads_100k_dicts, out_dir=FRAGMENTS_W4_DIR, num_fragments=8)

    edges_100k, job1_100k_metrics = run_job1_from_fragments(
        frags_100k, num_workers=4, num_reducers=4, use_combiner=True
    )
    node_summary_100k, job2_100k_metrics = run_job2_node_summary(
        edges_100k, num_workers=4, num_reducers=4, use_combiner=True, num_fragments=8
    )

    # También construir Node Summary del grafo Unidad 3 (10k) para comparabilidad exacta
    node_summary_u3, _ = run_job2_node_summary(
        mr_edges_w2, num_workers=4, num_reducers=4, use_combiner=True, num_fragments=8
    )

    # Persistir datasets JSON de Unidad 4 (template oficial del curso)
    EDGES_W4.parent.mkdir(parents=True, exist_ok=True)
    EDGES_W4.write_text(json.dumps(edges_100k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    NODE_SUMMARY_W4.write_text(
        json.dumps(node_summary_100k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 3) Task 3: Cost Analysis (combiner vs no combiner, 1x/2x/4x -> 10x + S10)
    cost_analysis = run_cost_analysis(s10_val, base_count=100_000)

    # 4) Task 4: Reducer Size (q) & Replication Rate (r) + R = 1, 2, 4, 8
    reducer_analysis = run_reducer_size_analysis(
        frags_100k, job1_100k_metrics, job2_100k_metrics, s10_val
    )

    # 5) Task 5 (S14): Skewed Hot Key (>=40% spam wave) + Salting/Combiner Mitigation
    s14_skew = run_s14_skew_and_mitigation(count=120_000, hot_category="Noticias", hot_share=0.45, seed=42)

    # Destacar categorías crecientes (net_flow > 0) con alta tasa de marcados para Panel F
    mean_flag = statistics.mean(n["flagged_frac"] for n in node_summary_100k)
    category_flow = []
    for n in node_summary_100k:
        growing = n["net_flow"] > 0
        high_flag = n["flagged_frac"] >= mean_flag
        quadrant = (
            "Alerta: Creciente + Alto Flag"
            if growing and high_flag
            else "Creciente · Riesgo Moderado"
            if growing
            else "Decreciente · Alto Flag"
            if high_flag
            else "Estable / Bajo Riesgo"
        )
        category_flow.append({
            **n,
            "growing": growing,
            "high_flag": high_flag,
            "quadrant": quadrant,
        })
    category_flow.sort(key=lambda x: (x["flagged_frac"], x["net_flow"]), reverse=True)

    return {
        "pipeline_validation": {
            "unit3_edge_validation": validation_u3,
            "job1_validation_metrics": job1_val_metrics,
            "scale_100k_metrics": {
                "uploads": job1_100k_metrics["input_uploads"],
                "fragments": job1_100k_metrics["num_fragments"],
                "workers": job1_100k_metrics["num_workers"],
                "edges": job1_100k_metrics["output_edges"],
                "transitions": job1_100k_metrics["total_transitions"],
                "job1_wall_ms": job1_100k_metrics["wall_time_ms"],
                "job2_wall_ms": job2_100k_metrics["wall_time_ms"],
                "net_flow_sum_check": job2_100k_metrics["net_flow_sum_check"],
            },
        },
        "s10_pagerank_mr": s10_val,
        "cost_analysis": cost_analysis,
        "reducer_analysis": reducer_analysis,
        "s14_skew_mitigation": s14_skew,
        "node_summary_100k": category_flow,
        "node_summary_unit3": node_summary_u3,
        "mean_flagged_frac": mean_flag,
    }
