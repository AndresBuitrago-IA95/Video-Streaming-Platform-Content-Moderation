"""Resultados estáticos del dashboard (todo lo que no depende del cursor del stream).

Se calcula una vez y se guarda en `static_results.json`; usa `--refresh` en aggregate_api.py
para recalcular (los tiempos de QuickSort dependen de la máquina).
"""
from __future__ import annotations

import json
import statistics

import numpy as np
import pandas as pd

import metrics_and_graphs as mg
from algorithms import hashing, markov, quicksort, reservoir
from algorithms.bloom import sized_filter
from algorithms.hyperloglog import HyperLogLog
from config import STATIC_CACHE, VIDEOS_W1

HASH_N = (250, 500, None)           # None = todos los videos pendientes de revisión
HASH_BUCKETS = (64, 128, 256)
SCENARIO_ORDER = ("original", "ordenado", "inverso")


def _capacity(videos: pd.DataFrame, growth: int = 10) -> dict:
    """W1 T1: uploads/s y almacenamiento de metadatos con crecimiento de usuarios ×10."""
    span = (videos["upload_time"].max() - videos["upload_time"].min()).total_seconds()
    recs = json.loads(VIDEOS_W1.read_text(encoding="utf-8"))
    bytes_per = statistics.mean(len(json.dumps(r, separators=(",", ":"), ensure_ascii=False)
                                    .encode("utf-8")) for r in recs)
    rate = len(videos) / span
    rate10 = rate * growth
    per_day = rate10 * 86400 * bytes_per
    return {"records": len(videos), "span_days": span / 86400, "uploads_per_sec": rate,
            "growth_factor": growth, "uploads_per_sec_growth": rate10,
            "avg_metadata_bytes": bytes_per, "storage_per_day_bytes": per_day,
            "storage_per_year_bytes": per_day * 365,
            "assumption": "El dataset se toma como la muestra de tráfico del periodo observado; "
                          "el crecimiento ×10 escala la tasa de llegada y el volumen de metadatos "
                          "(sin archivos de video)."}


def _hashing_panel(videos: pd.DataFrame) -> dict:
    """W1 T4: tabla hash por categoría (clave categoría#video_id) de videos pendientes de revisión."""
    pending = videos[videos["is_flagged"]]
    keys_all = (pending["category"] + "#" + pending["video_id"]).tolist()
    configs = {}
    for n in HASH_N:
        keys = keys_all if n is None else keys_all[:n]
        for m in HASH_BUCKETS:
            loads = {meth: hashing.bucket_loads(keys, m, meth) for meth in ("chaining", "two_choices")}
            hist = {meth: hashing.histogram(v) for meth, v in loads.items()}
            lo = min(min(h) for h in hist.values())
            hi = max(max(h) for h in hist.values())
            configs[f"{len(keys)}_{m}"] = {
                "n": len(keys), "buckets": m,
                "histogram": [{"load": x, "chaining": hist["chaining"].get(x, 0),
                               "two_choices": hist["two_choices"].get(x, 0)}
                              for x in range(lo, hi + 1)],
                "stats": {meth: {"max_load": max(v), "mean": statistics.mean(v),
                                 "std": statistics.pstdev(v), "empty_buckets": v.count(0),
                                 "theoretical_max": hashing.theoretical_max_load(len(keys), m, meth)}
                          for meth, v in loads.items()},
            }
    default = f"{len(keys_all)}_128"
    return {"key": "categoría#video_id", "population": "videos marcados (pendientes de revisión)",
            "default_config": default, "configs": configs,
            "sharding": hashing.shard_uploaders(videos["uploader_id"].tolist(), 32)}


def _quicksort_panel(videos: pd.DataFrame) -> dict:
    rows = quicksort.benchmark(videos["duration_sec"].astype(int).tolist())
    df = pd.DataFrame(rows)
    out = {}
    for s in SCENARIO_ORDER:
        w = df[df.scenario == s].pivot(index="n", columns="algorithm", values="mean_ms").reset_index()
        out[s] = [{"n": int(r.n), "deterministic_ms": float(r.determinista),
                   "randomized_ms": float(r.aleatorizado)} for r in w.itertuples()]
    worst = out["ordenado"][-1]
    return {"scenarios": out, "default_scenario": "ordenado", "unit": "ms",
            "worst_case_speedup": worst["deterministic_ms"] / worst["randomized_ms"],
            "verified_against_sorted": True}


def _bloom_final(stream: pd.DataFrame) -> list[dict]:
    flagged = {u for u, f in zip(stream["uploader_id"], stream["is_flagged"]) if f}
    negatives = sorted(set(stream["uploader_id"]) - flagged)
    rows = []
    for bits in (4, 8, 12, 16):
        bf = sized_filter(len(flagged), bits)
        for u in flagged:
            bf.add(u)
        fp = sum(u in bf for u in negatives)
        rows.append({"bits_per_element": bits, "hash_functions": bf.hashes, "inserted": len(flagged),
                     "negatives": len(negatives), "false_positives": fp,
                     "false_negatives": sum(u not in bf for u in flagged),
                     "fp_rate_experimental": fp / len(negatives),
                     "fp_rate_theoretical": bf.theoretical_fp()})
    return rows


def _hll_by_day(stream: pd.DataFrame) -> dict:
    """W2 T4: error relativo vs. memoria para m = 16, 32, 64, 128 (promedio sobre los días)."""
    day = stream["upload_time"].dt.date
    errs: dict[int, list[float]] = {16: [], 32: [], 64: [], 128: []}
    for _, g in stream.groupby(day):
        users = set(g["uploader_id"])
        for m in errs:
            h = HyperLogLog(m)
            for u in users:
                h.add_hash(hashing.stable_hash(u))
            errs[m].append(abs(h.estimate() - len(users)) / len(users))
    return {"days": int(day.nunique()),
            "rows": [{"m": m, "memory_bits": 6 * m, "mean_rel_error": statistics.mean(e),
                      "theoretical_error": 1.04 / m ** 0.5} for m, e in errs.items()]}


def _markov_panel(videos: pd.DataFrame, edges: pd.DataFrame) -> dict:
    P = mg.build_transition_matrix(edges)
    pr_df, pr_meta = mg.pagerank_vs_frequency(videos, P)
    pi, iters, resid = markov.stationary_distribution(P)

    # flagged_frac por categoría de origen, ponderado por transition_count
    w = edges.assign(w=edges["flagged_frac"] * edges["transition_count"]).groupby("from_category")
    flagged_frac = (w["w"].sum() / w["transition_count"].sum()).reindex(P.index)

    pr_df["flagged_frac"] = pr_df["category"].map(flagged_frac)
    lo, hi = pr_df["flagged_frac"].min(), pr_df["flagged_frac"].max()
    pr_df["flagged_scaled"] = 100 * (pr_df["flagged_frac"] - lo) / (hi - lo) if hi > lo else 50.0
    pr_df["stationary"] = pr_df["category"].map(pi)

    return {
        "pagerank_meta": pr_meta,
        "pagerank": pr_df,
        "classification": markov.classify_states(P),
        "stationary": {"iterations": iters, "residual": resid,
                       "top_category": pi.idxmax(), "top_value": float(pi.max()),
                       "raw_frequency_top": videos["category"].value_counts().idxmax()},
        "lazy_walk": markov.lazy_walk(P, pi, 50000),
        "two_sat": markov.moderation_policy(pi, flagged_frac),
    }


def build_static() -> dict:
    videos = mg.load_videos()
    stream = mg.load_stream()
    edges = mg.load_transitions()

    uploaders, chernoff_meta = mg.chernoff_uploader_analysis(videos)
    top = uploaders[uploaders["suspicious"]].head(10)
    if not len(top):
        top = uploaders.head(10)
    view_records = list(zip(stream["category"], stream["view_count_1h"].astype(float)))

    mk = _markov_panel(videos, edges)
    return {
        "meta": {"videos": int(len(videos)), "categories": int(videos["category"].nunique())},
        "capacity": _capacity(videos),
        "hashing": _hashing_panel(videos),
        "quicksort": _quicksort_panel(videos),
        "chernoff": {"summary": chernoff_meta,
                     "top_uploaders": top[["uploader_id", "videos", "flagged", "flag_rate",
                                           "chernoff_p_observed", "suspicious"]]
                     .to_dict("records")},
        "moments_overall": mg.category_moments(videos),
        "bloom_final": _bloom_final(stream),
        "hll_by_day": _hll_by_day(stream),
        "reservoir_view_count": reservoir.compare_sizes(view_records),
        "pagerank": {"meta": mk["pagerank_meta"], "categories": mk["pagerank"].to_dict("records")},
        "markov": {k: mk[k] for k in ("classification", "stationary", "lazy_walk", "two_sat")},
    }


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.generic,)):
        obj = obj.item()
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    return obj


def load_static(refresh: bool = False) -> dict:
    if not refresh and STATIC_CACHE.exists():
        return json.loads(STATIC_CACHE.read_text(encoding="utf-8"))
    print("Calculando resultados estáticos (una sola vez, ~30 s)…", flush=True)
    data = _clean(build_static())
    STATIC_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data
