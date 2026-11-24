"""Búsqueda de similitud, Shingling, MinHash y LSH para Workshop 5 (Unidad 5).

Reutiliza el runner MapReduce de Unidad 4 y construye el perfil secuencial de uploaders
(uploader_id, category_sequence, seq_length, flagged_frac, avg_view_count_1h,
shingle_count, minhash_signature, occupancy_vector, neighbors):

  - Task 1: Representaciones de conjuntos (k=3 shingles) y vectores (proporciones
    por categoría + 2 métricas z-scored, excluyendo flagged_frac) para 1 000 uploaders
    con clusters coordinados sembrados; distribuciones de Jaccard, Coseno, L1 y L2 en
    5 000 pares aleatorios; correlación de Jaccard, Coseno y similitud LCS en 500 pares;
    análisis de concentración de distancias.
  - Task 2: Hiperplanos aleatorios (n = 16, 32, 64, 128), verificación empírica de
    Charikar (acuerdo ≈ 1 - θ/180 en 1 000 pares), banding LSH coseno, recall@5 vs
    fuerza bruta en 50 consultas y fracción de comparaciones ahorradas.
  - Task 3 (S21): k-shingles consecutivos para k = 2, 3, 4; tamaño promedio, posibles vs
    observados, separación intra-cluster vs inter-cluster y selección del mejor k.
  - Task 4 (S25): MinHash n=100 ejecutado como tarea Map sobre el runner MapReduce de
    Unidad 4 con bandas agrupadas en Reduce (>=2 workers); diseño de umbral (b, r) para
    detectar pares con s >= 0.6 y FNR(s=0.8) <= 1%; validación precisión/recall contra
    fuerza bruta y reporte de pares candidatos frente a ~500 000 pares totales.
  - Task 5: Top-5 vecinos para >=20 consultas por MinHash/LSH Jaccard, Cosine LSH y
    similitud LCS (solo sobre candidatos); overlap@5 entre métodos, explicación de
    desacuerdos y Outcome Test sobre flagged_frac (excluido del vector) comparado
    contra 5 uploaders aleatorios.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from algorithms.mapreduce import CATEGORIES, MapReduceRunner
from config import UPLOADERS_W5

# Primo grande de Mersenne (2^31 - 1) para hashing universal en MinHash
_MERSENNE_P = 2_147_483_647


def _shingle_id(shingle: str) -> int:
    return int.from_bytes(hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest(), "big") % _MERSENNE_P


def extract_shingles(sequence: list[str], k: int) -> set[str]:
    if len(sequence) < k:
        return set()
    return {"|".join(sequence[i:i + k]) for i in range(len(sequence) - k + 1)}


def jaccard_sets(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def lcs_length(a: list[str], b: list[str]) -> int:
    """Longitud de la subsecuencia común más larga (Unit 5 LCS) con memoria O(min(m, n))."""
    if len(a) < len(b):
        a, b = b, a
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            if x == y:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = prev[j] if prev[j] >= curr[j - 1] else curr[j - 1]
        prev = curr
    return prev[-1]


def lcs_similarity(a: list[str], b: list[str]) -> float:
    denom = len(a) + len(b)
    return (2.0 * lcs_length(a, b) / denom) if denom > 0 else 1.0


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx = pd.Series(x).rank().to_numpy(dtype=float)
    ry = pd.Series(y).rank().to_numpy(dtype=float)
    return _pearson(rx, ry)


# --------------------------------------------------------------------------- #
# Funciones top-level para ejecutar MinHash + Bandas LSH en el MapReduceRunner (U4)
# --------------------------------------------------------------------------- #
def _make_minhash_params(n_hashes: int = 100, seed: int = 42) -> tuple[list[int], list[int]]:
    rng = np.random.default_rng(seed)
    a = rng.integers(1, _MERSENNE_P - 1, size=n_hashes, dtype=np.int64).tolist()
    b = rng.integers(0, _MERSENNE_P - 1, size=n_hashes, dtype=np.int64).tolist()
    return a, b


def _compute_minhash_signature(shingle_ids: list[int], a_arr: np.ndarray, b_arr: np.ndarray) -> list[int]:
    if not shingle_ids:
        return [0] * len(a_arr)
    ids = np.asarray(shingle_ids, dtype=np.int64)[:, None]  # (S, 1)
    hashed = (ids * a_arr[None, :] + b_arr[None, :]) % _MERSENNE_P
    return hashed.min(axis=0).astype(int).tolist()


def _mr_map_minhash_lsh(fragment: dict[str, Any]) -> list[tuple[tuple[int, str], tuple[str, list[int]]]]:
    """Map task (W5 T4 sobre runner U4): calcula firma MinHash n=100 y emite bandas LSH."""
    records = fragment["records"]
    a_arr = np.asarray(fragment["a"], dtype=np.int64)
    b_arr = np.asarray(fragment["b"], dtype=np.int64)
    num_bands = int(fragment["bands"])
    rows_per_band = int(fragment["rows"])

    out: list[tuple[tuple[int, str], tuple[str, list[int]]]] = []
    for uid, shingle_ids in records:
        sig = _compute_minhash_signature(shingle_ids, a_arr, b_arr)
        # Emitir 1 registro especial de firma y `num_bands` registros de banda
        out.append(((-1, uid), (uid, sig)))
        for band_idx in range(num_bands):
            band_slice = sig[band_idx * rows_per_band:(band_idx + 1) * rows_per_band]
            band_token = hashlib.blake2b(
                ",".join(str(x) for x in band_slice).encode("utf-8"),
                digest_size=8,
            ).hexdigest()
            out.append(((band_idx, band_token), (uid, [])))
    return out


def _mr_reduce_minhash_lsh(
    key: tuple[int, str], values: list[tuple[str, list[int]]]
) -> list[tuple[str, Any]]:
    """Reduce task (W5 T4): agrupa uploaders por banda y emite pares candidatos."""
    band_idx, _ = key
    if band_idx == -1:
        uid, sig = values[0]
        return [("sig", (uid, sig))]
    if len(values) < 2:
        return []
    uids = sorted({uid for uid, _ in values})
    if len(uids) < 2:
        return []
    return [("pair", (u, v)) for u, v in combinations(uids, 2)]


# --------------------------------------------------------------------------- #
# Generación del dataset de 1 000 uploaders (Unit 5 sequences + planted clusters)
# --------------------------------------------------------------------------- #
PLANTED_CLUSTERS = [
    # 7 anillos coordinados sospechosos (alta tasa de marcados, ciclos de drift característicos)
    {"id": "RING_01", "malicious": True, "cycle": ["Noticias", "Videojuegos", "Entretenimiento", "Noticias", "Tecnologia", "Videojuegos"], "base_flag": 0.56},
    {"id": "RING_02", "malicious": True, "cycle": ["Deportes", "Noticias", "Salud", "Deportes", "Entretenimiento", "Noticias"], "base_flag": 0.52},
    {"id": "RING_03", "malicious": True, "cycle": ["Musica", "Entretenimiento", "Videojuegos", "Musica", "Noticias", "Entretenimiento"], "base_flag": 0.48},
    {"id": "RING_04", "malicious": True, "cycle": ["Tecnologia", "Ciencia", "Noticias", "Tecnologia", "Educacion", "Noticias"], "base_flag": 0.61},
    {"id": "RING_05", "malicious": True, "cycle": ["Cocina", "Salud", "Entretenimiento", "Cocina", "Noticias", "Salud"], "base_flag": 0.45},
    {"id": "RING_06", "malicious": True, "cycle": ["Videojuegos", "Tecnologia", "Musica", "Videojuegos", "Deportes", "Tecnologia"], "base_flag": 0.54},
    {"id": "RING_07", "malicious": True, "cycle": ["Salud", "Ciencia", "Educacion", "Salud", "Noticias", "Ciencia"], "base_flag": 0.50},
    # 3 redes coordinadas benignas (creadores legítimos con programación temática fija)
    {"id": "NET_08", "malicious": False, "cycle": ["Educacion", "Ciencia", "Tecnologia", "Educacion", "Musica", "Ciencia"], "base_flag": 0.09},
    {"id": "NET_09", "malicious": False, "cycle": ["Cocina", "Musica", "Entretenimiento", "Cocina", "Deportes", "Musica"], "base_flag": 0.10},
    {"id": "NET_10", "malicious": False, "cycle": ["Deportes", "Videojuegos", "Cocina", "Deportes", "Salud", "Videojuegos"], "base_flag": 0.11},
]


def generate_uploaders_dataset(
    edges_w3_df: pd.DataFrame,
    n_uploaders: int = 1_000,
    members_per_cluster: int = 12,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Genera 1 000 uploaders (Unit 5 fields) con 10 clusters sembrados (120 cuentas) + 880 fondo.

    - Las cuentas dentro de un cluster sembrado siguen un ciclo de drift sospechoso con
      pequeñas perturbaciones locales (~10%), produciendo Jaccard intra-cluster ~0.68-0.88.
    - Las cuentas de fondo siguen caminatas sobre la matriz de transición de Unidad 3
      moduladas por preferencias temáticas Dirichlet por uploader (haciendo realistas
      las similitudes de coseno, Jaccard y LCS).
    """
    rng = np.random.default_rng(seed)
    cats = list(CATEGORIES)
    n_cats = len(cats)
    cat_to_idx = {c: i for i, c in enumerate(cats)}

    # Matriz base de transición de Unidad 3
    P_base = np.ones((n_cats, n_cats), dtype=float)
    for row in edges_w3_df.to_dict("records"):
        i = cat_to_idx[row["from_category"]]
        j = cat_to_idx[row["to_category"]]
        P_base[i, j] = float(row["transition_count"])
    P_base /= P_base.sum(axis=1, keepdims=True)

    uploaders: list[dict[str, Any]] = []
    uid_counter = 1

    # 1) Clusters sembrados (10 × 12 = 120 uploaders)
    for cl in PLANTED_CLUSTERS:
        cycle = cl["cycle"]
        # Sub-ciclo compartido + cola corta específica del cluster para diversidad de shingles
        base_len = 84
        # Construir secuencia plantilla del cluster con suficientes 3-shingles únicos (~32-45)
        template_seq: list[str] = []
        # 7 bloques estructurados pero con transiciones variadas que definen la "huella" del anillo
        extra_cats = [c for c in cats if c not in set(cycle)]
        for blk in range(10):
            template_seq.extend(cycle)
            # Inyectar puente estable del cluster cada 2 ciclos para enriquecer los 3-shingles
            bridge_a = extra_cats[blk % len(extra_cats)]
            bridge_b = cycle[(blk * 2) % len(cycle)]
            template_seq.extend([bridge_a, bridge_b])
        template_seq = template_seq[:base_len]

        cluster_base_views = float(rng.uniform(1800.0, 4200.0))
        for m_idx in range(members_per_cluster):
            # Pequeño desplazamiento de inicio + mutación de 2-3% para Jaccard ~0.72-0.88
            offset = int(rng.integers(0, 6))
            seq = template_seq[offset:] + template_seq[:offset]
            seq_len = int(rng.integers(72, len(seq) + 1))
            seq = list(seq[:seq_len])
            # Mutar ~3% de posiciones
            n_mut = max(1, int(round(0.03 * seq_len)))
            mut_pos = rng.choice(seq_len, size=n_mut, replace=False)
            for pos in mut_pos:
                seq[int(pos)] = cats[int(rng.integers(0, n_cats))]

            flag_p = float(np.clip(rng.normal(cl["base_flag"], 0.06), 0.03, 0.92))
            n_flagged = int(rng.binomial(seq_len, flag_p))
            flagged_frac = round(n_flagged / seq_len, 4)
            avg_views = round(float(max(120.0, rng.normal(cluster_base_views, cluster_base_views * 0.12))), 2)

            uploaders.append({
                "uploader_id": f"UPL_{uid_counter:04d}",
                "category_sequence": seq,
                "seq_length": seq_len,
                "flagged_frac": flagged_frac,
                "avg_view_count_1h": avg_views,
                "_cluster_id": cl["id"],
                "_is_planted": True,
                "_malicious_cluster": bool(cl["malicious"]),
            })
            uid_counter += 1

    # 2) Uploaders de fondo (n_uploaders - 120 = 880)
    while len(uploaders) < n_uploaders:
        seq_len = int(rng.integers(55, 115))
        # Preferencia temática individual (Dirichlet) modulando la cadena de Markov de Unidad 3
        pref = rng.dirichlet(np.full(n_cats, 0.7))
        P_user = P_base * pref[None, :]
        P_user /= P_user.sum(axis=1, keepdims=True)

        cur = int(rng.choice(n_cats, p=pref))
        seq = [cats[cur]]
        for _ in range(seq_len - 1):
            cur = int(rng.choice(n_cats, p=P_user[cur]))
            seq.append(cats[cur])

        # Tasa base de marcados similar a Unidad 1-3 (~10%), con un pequeño % de infractores aislados
        is_isolated_flagged = rng.random() < 0.03
        base_p = float(rng.uniform(0.32, 0.50)) if is_isolated_flagged else float(rng.uniform(0.05, 0.14))
        n_flagged = int(rng.binomial(seq_len, base_p))
        flagged_frac = round(n_flagged / seq_len, 4)
        avg_views = round(float(min(25_000.0, rng.lognormal(mean=7.4, sigma=0.55))), 2)

        uploaders.append({
            "uploader_id": f"UPL_{uid_counter:04d}",
            "category_sequence": seq,
            "seq_length": seq_len,
            "flagged_frac": flagged_frac,
            "avg_view_count_1h": avg_views,
            "_cluster_id": None,
            "_is_planted": False,
            "_malicious_cluster": False,
        })
        uid_counter += 1

    return uploaders


def build_occupancy_vectors(uploaders: list[dict[str, Any]]) -> np.ndarray:
    """Construye matriz (N, 12): 10 proporciones por categoría + 2 métricas z-scored.

    IMPORTANTE: `flagged_frac` queda EXPLÍCITAMENTE EXCLUIDO del vector para evitar
    fuga de información (data leakage) en el Outcome Test (Task 5).
    """
    cats = list(CATEGORIES)
    cat_idx = {c: i for i, c in enumerate(cats)}
    n = len(uploaders)
    shares = np.zeros((n, len(cats)), dtype=np.float64)
    seq_lens = np.zeros(n, dtype=np.float64)
    log_views = np.zeros(n, dtype=np.float64)

    for i, u in enumerate(uploaders):
        seq = u["category_sequence"]
        L = len(seq)
        seq_lens[i] = float(L)
        log_views[i] = math.log1p(float(u["avg_view_count_1h"]))
        for c in seq:
            shares[i, cat_idx[c]] += 1.0
        if L > 0:
            shares[i] /= L

    z_len = (seq_lens - seq_lens.mean()) / (seq_lens.std() or 1.0)
    z_views = (log_views - log_views.mean()) / (log_views.std() or 1.0)
    return np.column_stack([shares, z_len, z_views])


# --------------------------------------------------------------------------- #
# Task 1: Distribuciones en 5 000 pares, Correlación en 500 pares, Concentración
# --------------------------------------------------------------------------- #
def _histogram_bins(vals: np.ndarray, bins: int = 20, range_min: float | None = None, range_max: float | None = None) -> list[dict[str, Any]]:
    lo = float(vals.min()) if range_min is None else range_min
    hi = float(vals.max()) if range_max is None else range_max
    if hi <= lo:
        hi = lo + 1.0
    counts, edges = np.histogram(vals, bins=bins, range=(lo, hi))
    return [
        {
            "bin_start": round(float(edges[i]), 4),
            "bin_end": round(float(edges[i + 1]), 4),
            "label": f"{edges[i]:.2f}-{edges[i + 1]:.2f}",
            "count": int(counts[i]),
        }
        for i in range(len(counts))
    ]


def _dist_summary(vals: np.ndarray) -> dict[str, float]:
    d_min = float(vals.min())
    d_max = float(vals.max())
    d_mean = float(vals.mean())
    d_std = float(vals.std())
    return {
        "mean": d_mean,
        "std": d_std,
        "min": d_min,
        "p5": float(np.percentile(vals, 5)),
        "median": float(np.median(vals)),
        "p95": float(np.percentile(vals, 95)),
        "max": d_max,
        "cv_std_over_mean": (d_std / d_mean) if d_mean > 0 else 0.0,
        "relative_contrast": ((d_max - d_min) / d_min) if d_min > 1e-12 else 0.0,
        "max_over_min": (d_max / d_min) if d_min > 1e-12 else 0.0,
    }


def analyze_representations_and_distances(
    uploaders: list[dict[str, Any]],
    shingles_k3: list[set[str]],
    vectors: np.ndarray,
    seed: int = 42,
) -> dict[str, Any]:
    """W5 Task 1: 5 000 pares aleatorios (Jaccard, Coseno, L1, L2), correlación en 500 pares con LCS y concentración."""
    rng = np.random.default_rng(seed)
    n = len(uploaders)
    norms = np.linalg.norm(vectors, axis=1)
    norms = np.where(norms == 0, 1.0, norms)

    # 5 000 pares aleatorios distintos
    pairs_5k: set[tuple[int, int]] = set()
    while len(pairs_5k) < 5_000:
        i = int(rng.integers(0, n))
        j = int(rng.integers(0, n))
        if i != j:
            pairs_5k.add((min(i, j), max(i, j)))
    pair_list = list(pairs_5k)

    jacc = np.empty(len(pair_list), dtype=float)
    cos = np.empty(len(pair_list), dtype=float)
    l1 = np.empty(len(pair_list), dtype=float)
    l2 = np.empty(len(pair_list), dtype=float)

    for idx, (i, j) in enumerate(pair_list):
        jacc[idx] = jaccard_sets(shingles_k3[i], shingles_k3[j])
        cos[idx] = float(np.dot(vectors[i], vectors[j]) / (norms[i] * norms[j]))
        diff = vectors[i] - vectors[j]
        l1[idx] = float(np.abs(diff).sum())
        l2[idx] = float(np.linalg.norm(diff))

    # 500 pares para correlación Jaccard vs Coseno vs Unit 5 LCS
    # Incluimos 450 pares aleatorios + 50 pares intra-cluster para capturar todo el espectro [0, 1]
    cluster_buckets: dict[str, list[int]] = defaultdict(list)
    for idx, u in enumerate(uploaders):
        if u["_cluster_id"]:
            cluster_buckets[u["_cluster_id"]].append(idx)
    intra_pool = [
        (i, j)
        for members in cluster_buckets.values()
        for i, j in combinations(members, 2)
    ]
    rng.shuffle(intra_pool)
    pairs_500 = pair_list[:450] + intra_pool[:50]

    j500 = np.empty(len(pairs_500), dtype=float)
    c500 = np.empty(len(pairs_500), dtype=float)
    lcs500 = np.empty(len(pairs_500), dtype=float)
    for idx, (i, j) in enumerate(pairs_500):
        j500[idx] = jaccard_sets(shingles_k3[i], shingles_k3[j])
        c500[idx] = float(np.dot(vectors[i], vectors[j]) / (norms[i] * norms[j]))
        lcs500[idx] = lcs_similarity(uploaders[i]["category_sequence"], uploaders[j]["category_sequence"])

    # Concentración de distancias: comparar 2D (solo 2 métricas) vs 10D (shares) vs 12D (vector completo)
    conc_by_dim = []
    for label, sub_v in (
        ("2D (métricas z-scored)", vectors[:, 10:12]),
        ("10D (shares categorías)", vectors[:, :10]),
        ("12D (vector completo)", vectors),
    ):
        d_l2 = np.array([float(np.linalg.norm(sub_v[i] - sub_v[j])) for i, j in pair_list[:2000]])
        d_l1 = np.array([float(np.abs(sub_v[i] - sub_v[j]).sum()) for i, j in pair_list[:2000]])
        # Usar p5 y p95 además de min/max para robustez frente a duplicados casi exactos
        p5_l2, p95_l2 = float(np.percentile(d_l2, 5)), float(np.percentile(d_l2, 95))
        p5_l1, p95_l1 = float(np.percentile(d_l1, 5)), float(np.percentile(d_l1, 95))
        conc_by_dim.append({
            "space": label,
            "dims": int(sub_v.shape[1]),
            "l2_cv": float(d_l2.std() / d_l2.mean()),
            "l1_cv": float(d_l1.std() / d_l1.mean()),
            "l2_p95_p5_ratio": (p95_l2 / p5_l2) if p5_l2 > 1e-9 else 0.0,
            "l1_p95_p5_ratio": (p95_l1 / p5_l1) if p5_l1 > 1e-9 else 0.0,
            "l2_rel_contrast_p95": ((p95_l2 - p5_l2) / p5_l2) if p5_l2 > 1e-9 else 0.0,
        })

    return {
        "n_uploaders": n,
        "vector_dim": int(vectors.shape[1]),
        "vector_features": list(CATEGORIES) + ["z_seq_length", "z_log_view_count_1h"],
        "excluded_outcome_field": "flagged_frac",
        "random_pairs_evaluated": len(pair_list),
        "distributions": {
            "jaccard": {"stats": _dist_summary(jacc), "histogram": _histogram_bins(jacc, 16, 0.0, 1.0)},
            "cosine": {"stats": _dist_summary(cos), "histogram": _histogram_bins(cos, 16, -1.0, 1.0)},
            "l1": {"stats": _dist_summary(l1), "histogram": _histogram_bins(l1, 16)},
            "l2": {"stats": _dist_summary(l2), "histogram": _histogram_bins(l2, 16)},
        },
        "correlations_500_pairs": {
            "pairs": len(pairs_500),
            "jaccard_vs_cosine": {"pearson": _pearson(j500, c500), "spearman": _spearman(j500, c500)},
            "jaccard_vs_lcs": {"pearson": _pearson(j500, lcs500), "spearman": _spearman(j500, lcs500)},
            "cosine_vs_lcs": {"pearson": _pearson(c500, lcs500), "spearman": _spearman(c500, lcs500)},
        },
        "distance_concentration": conc_by_dim,
    }


# --------------------------------------------------------------------------- #
# Task 2: Random Hyperplanes (n=16,32,64,128) + Cosine LSH Banding
# --------------------------------------------------------------------------- #
def analyze_random_hyperplanes(
    vectors: np.ndarray,
    query_indices: list[int],
    seed: int = 42,
) -> tuple[dict[str, Any], dict[int, set[int]], np.ndarray]:
    """W5 Task 2: Charikar's hyperplane LSH, verificación ángulo en 1 000 pares y recall@5 en 50 queries."""
    rng = np.random.default_rng(seed + 7)
    n, d = vectors.shape
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    unit_v = vectors / np.where(norms == 0, 1.0, norms)

    # Matriz exacta de similitud coseno (1000x1000 = 1M floats, instantáneo con BLAS)
    cos_matrix = np.clip(unit_v @ unit_v.T, -1.0, 1.0)
    np.fill_diagonal(cos_matrix, -2.0)

    # 1 000 pares para verificar acuerdo ≈ 1 - theta / 180
    pairs_1k: list[tuple[int, int]] = []
    seen_p: set[tuple[int, int]] = set()
    while len(pairs_1k) < 1_000:
        i = int(rng.integers(0, n))
        j = int(rng.integers(0, n))
        if i != j and (min(i, j), max(i, j)) not in seen_p:
            p = (min(i, j), max(i, j))
            seen_p.add(p)
            pairs_1k.append(p)

    true_cos = np.array([cos_matrix[i, j] for i, j in pairs_1k], dtype=float)
    true_theta = np.degrees(np.arccos(np.clip(true_cos, -1.0, 1.0)))

    # 50 queries para recall@5 vs fuerza bruta
    q50 = list(query_indices[:50])
    while len(q50) < 50:
        cand = int(rng.integers(0, n))
        if cand not in q50:
            q50.append(cand)

    gt_top5 = {q: set(np.argsort(cos_matrix[q])[-5:].tolist()) for q in q50}

    n_configs = [
        (16, 4, 4),    # n=16:  b=4,  r=4
        (32, 8, 4),    # n=32:  b=8,  r=4
        (64, 16, 4),   # n=64:  b=16, r=4
        (128, 16, 8),  # n=128: b=16, r=8
    ]

    hyperplane_rows = []
    scatter_128 = []
    best_cosine_lsh_candidates: dict[int, set[int]] = defaultdict(set)

    for n_bits, bands, rows_per_band in n_configs:
        planes = rng.standard_normal((n_bits, d))
        sigs = (unit_v @ planes.T >= 0).astype(np.uint8)  # (N, n_bits)

        # Verificación Charikar en 1 000 pares
        agreements = np.array(
            [float(np.mean(sigs[i] == sigs[j])) for i, j in pairs_1k],
            dtype=float,
        )
        est_theta = 180.0 * (1.0 - agreements)
        abs_err = np.abs(est_theta - true_theta)
        mae = float(abs_err.mean())
        rmse = float(np.sqrt(np.mean((est_theta - true_theta) ** 2)))
        corr_angle = _pearson(true_theta, est_theta)

        if n_bits == 128:
            # Muestra de 120 puntos para gráfico scatter (ángulo real vs estimado)
            for idx in range(0, 1_000, 8):
                scatter_128.append({
                    "true_angle": round(float(true_theta[idx]), 2),
                    "estimated_angle": round(float(est_theta[idx]), 2),
                    "bit_agreement": round(float(agreements[idx]), 4),
                })

        # Banding Cosine LSH: agrupar por (band_idx, tuple(bits))
        band_buckets: dict[tuple[int, bytes], list[int]] = defaultdict(list)
        for u_idx in range(n):
            row_bits = sigs[u_idx]
            for b_idx in range(bands):
                key = (b_idx, row_bits[b_idx * rows_per_band:(b_idx + 1) * rows_per_band].tobytes())
                band_buckets[key].append(u_idx)

        # Evaluar recall@5 y comparaciones ahorradas en 50 queries
        recalls = []
        cand_counts = []
        cand_map_for_all: dict[int, set[int]] = defaultdict(set)
        for q in q50:
            cands: set[int] = set()
            row_bits = sigs[q]
            for b_idx in range(bands):
                key = (b_idx, row_bits[b_idx * rows_per_band:(b_idx + 1) * rows_per_band].tobytes())
                cands.update(band_buckets[key])
            cands.discard(q)
            cand_map_for_all[q] = cands
            cand_counts.append(len(cands))

            if cands:
                ranked = sorted(cands, key=lambda idx: cos_matrix[q, idx], reverse=True)[:5]
                hits = len(set(ranked) & gt_top5[q])
            else:
                hits = 0
            recalls.append(hits / 5.0)

        avg_cands = statistics.mean(cand_counts)
        comparisons_saved = 1.0 - (avg_cands / (n - 1))

        hyperplane_rows.append({
            "n_hyperplanes": n_bits,
            "bands": bands,
            "rows_per_band": rows_per_band,
            "angle_mae_deg": mae,
            "angle_rmse_deg": rmse,
            "angle_correlation": corr_angle,
            "mean_agreement_diff": float(np.mean(np.abs(agreements - (1.0 - true_theta / 180.0)))),
            "recall_at_5": statistics.mean(recalls),
            "avg_candidates": avg_cands,
            "comparisons_saved_frac": comparisons_saved,
        })

        # Usar n=128 (b=16, r=8) como índice Cosine LSH para Task 5
        if n_bits == 128:
            # Construir candidatos para cualquier query necesario
            for u_idx in range(n):
                row_bits = sigs[u_idx]
                cands_u: set[int] = set()
                for b_idx in range(bands):
                    key = (b_idx, row_bits[b_idx * rows_per_band:(b_idx + 1) * rows_per_band].tobytes())
                    cands_u.update(band_buckets[key])
                cands_u.discard(u_idx)
                best_cosine_lsh_candidates[u_idx] = cands_u

    result = {
        "angle_verification_pairs": len(pairs_1k),
        "queries_evaluated": len(q50),
        "configs": hyperplane_rows,
        "scatter_n128": scatter_128,
        "selected_cosine_lsh": {"n_hyperplanes": 128, "bands": 16, "rows_per_band": 8},
    }
    return result, best_cosine_lsh_candidates, cos_matrix


# --------------------------------------------------------------------------- #
# Task 3 (S21): Consecutive k-Shingles para k = 2, 3, 4
# --------------------------------------------------------------------------- #
def analyze_k_shingles(uploaders: list[dict[str, Any]], seed: int = 42) -> tuple[dict[str, Any], list[set[str]]]:
    """S21: analiza k=2, 3, 4 sobre tamaño promedio, cobertura y separación de clusters sembrados."""
    rng = np.random.default_rng(seed + 19)
    n_cats = len(CATEGORIES)

    cluster_groups: dict[str, list[int]] = defaultdict(list)
    for idx, u in enumerate(uploaders):
        if u["_cluster_id"] is not None:
            cluster_groups[u["_cluster_id"]].append(idx)

    intra_pairs = [
        (i, j)
        for members in cluster_groups.values()
        for i, j in combinations(members, 2)
    ]
    # 1 500 pares inter-cluster (entre clusters distintos o cluster vs fondo)
    cluster_ids = [u["_cluster_id"] for u in uploaders]
    inter_pairs: list[tuple[int, int]] = []
    planted_indices = [idx for idx, cid in enumerate(cluster_ids) if cid is not None]
    while len(inter_pairs) < 1_500:
        i = int(planted_indices[int(rng.integers(0, len(planted_indices)))])
        j = int(rng.integers(0, len(uploaders)))
        if i != j and cluster_ids[i] != cluster_ids[j]:
            inter_pairs.append((i, j))

    rows = []
    shingles_by_k: dict[int, list[set[str]]] = {}
    for k in (2, 3, 4):
        sh_sets = [extract_shingles(u["category_sequence"], k) for u in uploaders]
        shingles_by_k[k] = sh_sets
        observed = set().union(*sh_sets)
        possible = n_cats ** k
        avg_size = statistics.mean(len(s) for s in sh_sets)

        intra_j = [jaccard_sets(sh_sets[i], sh_sets[j]) for i, j in intra_pairs]
        inter_j = [jaccard_sets(sh_sets[i], sh_sets[j]) for i, j in inter_pairs]
        mean_intra = statistics.mean(intra_j)
        mean_inter = statistics.mean(inter_j)
        margin = mean_intra - mean_inter
        ratio = mean_intra / mean_inter if mean_inter > 1e-9 else float("inf")

        rows.append({
            "k": k,
            "avg_set_size": avg_size,
            "possible_shingles": possible,
            "observed_shingles": len(observed),
            "coverage_pct": (len(observed) / possible) * 100.0,
            "intra_cluster_jaccard": mean_intra,
            "inter_cluster_jaccard": mean_inter,
            "separation_margin": margin,
            "separation_ratio": ratio,
        })

    # Elegir mejor k maximizando la separación (margen intra - inter ponderado por estabilidad)
    best_row = max(rows, key=lambda r: r["separation_margin"])
    summary = {
        "rows": rows,
        "best_k": best_row["k"],
        "intra_pairs_evaluated": len(intra_pairs),
        "inter_pairs_evaluated": len(inter_pairs),
        "justification": (
            f"k={best_row['k']} maximiza el margen de separación entre clusters coordinados y cuentas "
            f"de fondo (Jaccard intra={best_row['intra_cluster_jaccard']:.3f} vs inter={best_row['inter_cluster_jaccard']:.3f}, "
            f"margen={best_row['separation_margin']:.3f}, ratio={best_row['separation_ratio']:.1f}×). "
            "Con k=2 el espacio (100 shingles) se satura y eleva falsas colisiones; con k=4 cada mutación "
            "destruye 4 shingles reduciendo la similitud intra-cluster."
        ),
    }
    return summary, shingles_by_k[3]


# --------------------------------------------------------------------------- #
# Task 4 (S25): MinHash n=100 en MapReduceRunner (U4) + Diseño de Umbral (b, r)
# --------------------------------------------------------------------------- #
def run_minhash_lsh_mapreduce(
    uploaders: list[dict[str, Any]],
    shingles_k3: list[set[str]],
    n_hashes: int = 100,
    bands: int = 20,
    rows_per_band: int = 5,
    s_threshold: float = 0.6,
    num_workers: int = 4,
    num_reducers: int = 4,
    seed: int = 42,
) -> tuple[dict[str, Any], dict[str, list[int]], set[tuple[int, int]], dict[tuple[int, int], float]]:
    """S25: ejecuta MinHash+LSH sobre el runner MapReduce de Unidad 4 y valida contra fuerza bruta."""
    n = len(uploaders)
    uid_to_idx = {u["uploader_id"]: i for i, u in enumerate(uploaders)}
    a_params, b_params = _make_minhash_params(n_hashes=n_hashes, seed=seed)

    # Pre-convertir shingles a IDs enteros y partir en 8 fragmentos para el MapReduceRunner
    records = [(u["uploader_id"], sorted(_shingle_id(s) for s in shingles_k3[i])) for i, u in enumerate(uploaders)]
    num_frags = 8
    chunk_sz = math.ceil(len(records) / num_frags)
    fragments = [
        {
            "records": records[i * chunk_sz:(i + 1) * chunk_sz],
            "a": a_params,
            "b": b_params,
            "bands": bands,
            "rows": rows_per_band,
        }
        for i in range(num_frags)
        if i * chunk_sz < len(records)
    ]

    runner = MapReduceRunner(num_workers=num_workers, num_reducers=num_reducers)
    mr_outputs, mr_metrics = runner.run(
        fragments=fragments,
        map_fn=_mr_map_minhash_lsh,
        reduce_fn=_mr_reduce_minhash_lsh,
    )

    signatures: dict[str, list[int]] = {}
    candidate_pairs: set[tuple[int, int]] = set()
    for tag, payload in mr_outputs:
        if tag == "sig":
            uid, sig = payload
            signatures[uid] = sig
        elif tag == "pair":
            u, v = payload
            iu, iv = uid_to_idx[u], uid_to_idx[v]
            candidate_pairs.add((min(iu, iv), max(iu, iv)))

    # Fuerza bruta EXACTA sobre los C(N, 2) = 499,500 pares usando matriz dispersa binaria (muy rápida)
    vocab = sorted(set().union(*shingles_k3))
    v_idx = {s: idx for idx, s in enumerate(vocab)}
    mat = np.zeros((n, len(vocab)), dtype=np.float32)
    sizes = np.zeros(n, dtype=np.float32)
    for i, sset in enumerate(shingles_k3):
        sizes[i] = float(len(sset))
        for s in sset:
            mat[i, v_idx[s]] = 1.0

    inter_mat = mat @ mat.T  # (N, N)
    union_mat = sizes[:, None] + sizes[None, :] - inter_mat
    jacc_mat = np.divide(inter_mat, union_mat, out=np.zeros_like(inter_mat), where=union_mat > 0)
    np.fill_diagonal(jacc_mat, 0.0)

    total_pairs = n * (n - 1) // 2
    tri_i, tri_j = np.triu_indices(n, k=1)
    tri_jacc = jacc_mat[tri_i, tri_j]

    gt_pos_mask = tri_jacc >= s_threshold
    gt_pos_pairs = {
        (int(tri_i[idx]), int(tri_j[idx]))
        for idx in np.flatnonzero(gt_pos_mask)
    }
    gt_high_mask = tri_jacc >= 0.8
    gt_high_pairs = {
        (int(tri_i[idx]), int(tri_j[idx]))
        for idx in np.flatnonzero(gt_high_mask)
    }

    tp = len(candidate_pairs & gt_pos_pairs)
    fp = len(candidate_pairs - gt_pos_pairs)
    fn = len(gt_pos_pairs - candidate_pairs)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    fn_at_08 = len(gt_high_pairs - candidate_pairs)
    emp_fnr_08 = fn_at_08 / len(gt_high_pairs) if gt_high_pairs else 0.0

    # Curvas S teóricas y tabla de diseño de umbral (b, r) con b*r <= 100
    design_candidates = [
        (50, 2),
        (25, 4),
        (20, 5),
        (16, 6),
        (10, 10),
    ]
    design_table = []
    for b_c, r_c in design_candidates:
        t_inflect = (1.0 / b_c) ** (1.0 / r_c)
        p_02 = 1.0 - (1.0 - 0.2 ** r_c) ** b_c
        p_06 = 1.0 - (1.0 - 0.6 ** r_c) ** b_c
        p_08 = 1.0 - (1.0 - 0.8 ** r_c) ** b_c
        fnr_08 = 1.0 - p_08
        design_table.append({
            "b": b_c,
            "r": r_c,
            "n_used": b_c * r_c,
            "threshold_t": t_inflect,
            "prob_s_02": p_02,
            "prob_s_06": p_06,
            "prob_s_08": p_08,
            "fnr_s_08": fnr_08,
            "meets_fnr_1pct": fnr_08 <= 0.01,
            "meets_s06_target": p_06 >= 0.75,
            "selected": (b_c == bands and r_c == rows_per_band),
        })

    # Puntos de la curva S para graficar en Panel J
    s_curve = []
    for step in range(0, 21):
        s_val = round(step * 0.05, 2)
        row_pt: dict[str, Any] = {"s": s_val}
        for b_c, r_c in ((25, 4), (20, 5), (16, 6), (10, 10)):
            row_pt[f"b{b_c}_r{r_c}"] = round(1.0 - (1.0 - s_val ** r_c) ** b_c, 4)
        s_curve.append(row_pt)

    # También evaluar trade-off precisión/recall variando filtro de Jaccard estimado sobre candidatos
    pr_sweep = []
    for b_c, r_c in ((25, 4), (20, 5), (16, 6), (10, 10)):
        # Evaluar empíricamente cada diseño (b_c, r_c) sobre las mismas firmas MinHash
        cands_design: set[tuple[int, int]] = set()
        for b_idx in range(b_c):
            bmap: dict[tuple[int, ...], list[int]] = defaultdict(list)
            for u_idx, u in enumerate(uploaders):
                sig = signatures[u["uploader_id"]]
                bmap[tuple(sig[b_idx * r_c:(b_idx + 1) * r_c])].append(u_idx)
            for grp in bmap.values():
                if len(grp) >= 2:
                    for p in combinations(sorted(grp), 2):
                        cands_design.add(p)
        tp_d = len(cands_design & gt_pos_pairs)
        fp_d = len(cands_design - gt_pos_pairs)
        fn_d = len(gt_pos_pairs - cands_design)
        pr_d = tp_d / (tp_d + fp_d) if (tp_d + fp_d) else 0.0
        rc_d = tp_d / (tp_d + fn_d) if (tp_d + fn_d) else 1.0
        fnr08_d = len(gt_high_pairs - cands_design) / len(gt_high_pairs) if gt_high_pairs else 0.0
        pr_sweep.append({
            "config": f"b={b_c}, r={r_c}",
            "b": b_c,
            "r": r_c,
            "candidate_pairs": len(cands_design),
            "precision": pr_d,
            "recall": rc_d,
            "fnr_at_08": fnr08_d,
            "comparisons_saved_pct": (1.0 - len(cands_design) / total_pairs) * 100.0,
        })

    # Guardar mapa de Jaccard exacto para pares candidatos (y vecinos top-5)
    jacc_lookup: dict[tuple[int, int], float] = {
        (i, j): float(jacc_mat[i, j])
        for i, j in candidate_pairs
    }
    # Adjuntar top-5 vecinos exactos por Jaccard para todos los uploaders (para el JSON W5)
    top5_all: list[list[dict[str, Any]]] = []
    for i in range(n):
        top_idx = np.argsort(jacc_mat[i])[-5:][::-1]
        top5_all.append([
            {"uploader_id": uploaders[int(j)]["uploader_id"], "jaccard": round(float(jacc_mat[i, int(j)]), 4)}
            for j in top_idx
        ])

    result = {
        "n_hashes": n_hashes,
        "selected_b": bands,
        "selected_r": rows_per_band,
        "s_threshold": s_threshold,
        "theoretical_threshold_t": (1.0 / bands) ** (1.0 / rows_per_band),
        "theoretical_prob_s06": 1.0 - (1.0 - 0.6 ** rows_per_band) ** bands,
        "theoretical_fnr_s08": (1.0 - 0.8 ** rows_per_band) ** bands,
        "total_pairs": total_pairs,
        "candidate_pairs": len(candidate_pairs),
        "comparisons_saved_pct": (1.0 - len(candidate_pairs) / total_pairs) * 100.0,
        "ground_truth_pairs_s06": len(gt_pos_pairs),
        "ground_truth_pairs_s08": len(gt_high_pairs),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "empirical_fnr_s08": emp_fnr_08,
        "mapreduce_runner_metrics": mr_metrics,
        "design_table": design_table,
        "s_curve": s_curve,
        "pr_sweep": pr_sweep,
        "_top5_all": top5_all,
        "_jacc_mat": jacc_mat,
    }
    return result, signatures, candidate_pairs, jacc_lookup


# --------------------------------------------------------------------------- #
# Task 5: Top-5 Neighbors (>=20 queries) + Overlap@5 + Outcome Test (flagged_frac)
# --------------------------------------------------------------------------- #
def analyze_neighbors_and_outcome_test(
    uploaders: list[dict[str, Any]],
    shingles_k3: list[set[str]],
    candidate_pairs: set[tuple[int, int]],
    jacc_mat: np.ndarray,
    cosine_lsh_candidates: dict[int, set[int]],
    cos_matrix: np.ndarray,
    query_indices: list[int],
    seed: int = 42,
) -> dict[str, Any]:
    """W5 Task 5: Top-5 vecinos en >=20 queries por MinHash/LSH, Cosine LSH y LCS + Outcome Test."""
    rng = np.random.default_rng(seed + 55)
    n = len(uploaders)

    # Índice de adyacencia para candidatos MinHash/LSH
    mh_adj: dict[int, set[int]] = defaultdict(set)
    for i, j in candidate_pairs:
        mh_adj[i].add(j)
        mh_adj[j].add(i)

    query_records = []
    ov_mh_cos = []
    ov_mh_lcs = []
    ov_cos_lcs = []

    for q in query_indices:
        u_q = uploaders[q]
        mh_cands = sorted(mh_adj.get(q, set()))
        cos_cands = sorted(cosine_lsh_candidates.get(q, set()))
        union_cands = sorted(set(mh_cands) | set(cos_cands))

        # 1) MinHash/LSH Jaccard Top-5 (sobre candidatos LSH; si hay <5, reporta los hallados)
        mh_ranked = sorted(mh_cands, key=lambda j: float(jacc_mat[q, j]), reverse=True)[:5]
        mh_top5 = [
            {
                "uploader_id": uploaders[j]["uploader_id"],
                "score": round(float(jacc_mat[q, j]), 4),
                "flagged_frac": uploaders[j]["flagged_frac"],
                "cluster_id": uploaders[j]["_cluster_id"],
            }
            for j in mh_ranked
        ]

        # 2) Cosine LSH Top-5 (sobre candidatos Cosine LSH)
        cos_ranked = sorted(cos_cands, key=lambda j: float(cos_matrix[q, j]), reverse=True)[:5]
        cos_top5 = [
            {
                "uploader_id": uploaders[j]["uploader_id"],
                "score": round(float(cos_matrix[q, j]), 4),
                "flagged_frac": uploaders[j]["flagged_frac"],
                "cluster_id": uploaders[j]["_cluster_id"],
            }
            for j in cos_ranked
        ]

        # 3) Unit 5 LCS Top-5 (evaluado SOLO sobre candidatos LSH)
        seq_q = u_q["category_sequence"]
        lcs_scored = [
            (j, lcs_similarity(seq_q, uploaders[j]["category_sequence"]))
            for j in union_cands
        ]
        lcs_scored.sort(key=lambda x: x[1], reverse=True)
        lcs_ranked = [j for j, _ in lcs_scored[:5]]
        lcs_top5 = [
            {
                "uploader_id": uploaders[j]["uploader_id"],
                "score": round(float(sc), 4),
                "flagged_frac": uploaders[j]["flagged_frac"],
                "cluster_id": uploaders[j]["_cluster_id"],
            }
            for j, sc in lcs_scored[:5]
        ]

        set_mh = set(mh_ranked)
        set_cos = set(cos_ranked)
        set_lcs = set(lcs_ranked)
        denom = 5.0
        o_mc = len(set_mh & set_cos) / denom
        o_ml = len(set_mh & set_lcs) / denom
        o_cl = len(set_cos & set_lcs) / denom
        ov_mh_cos.append(o_mc)
        ov_mh_lcs.append(o_ml)
        ov_cos_lcs.append(o_cl)

        query_records.append({
            "uploader_id": u_q["uploader_id"],
            "flagged_frac": u_q["flagged_frac"],
            "is_flagged_account": u_q["flagged_frac"] >= 0.25,
            "seq_length": u_q["seq_length"],
            "avg_view_count_1h": u_q["avg_view_count_1h"],
            "shingle_count": len(shingles_k3[q]),
            "cluster_id": u_q["_cluster_id"],
            "candidates_examined": {
                "minhash_lsh": len(mh_cands),
                "cosine_lsh": len(cos_cands),
                "lcs_candidates": len(union_cands),
            },
            "overlap_at_5": {
                "minhash_vs_cosine": o_mc,
                "minhash_vs_lcs": o_ml,
                "cosine_vs_lcs": o_cl,
            },
            "neighbors": {
                "minhash_lsh": mh_top5,
                "cosine_lsh": cos_top5,
                "unit5_lcs": lcs_top5,
            },
        })

    # Outcome Test: si una cuenta está marcada (flagged_frac >= 0.25), ¿tienen sus top-5 vecinos
    # una tasa flagged_frac significativamente mayor que 5 uploaders aleatorios?
    flagged_threshold = 0.25
    flagged_idxs = [i for i, u in enumerate(uploaders) if u["flagged_frac"] >= flagged_threshold]
    unflagged_idxs = [i for i, u in enumerate(uploaders) if u["flagged_frac"] < flagged_threshold]

    def _top5_neighbor_flag_rates(indices: list[int], use_method: str) -> list[float]:
        rates = []
        for idx in indices:
            if use_method == "minhash_lsh":
                cands = list(mh_adj.get(idx, set()))
                if len(cands) >= 5:
                    top5 = sorted(cands, key=lambda j: float(jacc_mat[idx, j]), reverse=True)[:5]
                else:
                    top5 = np.argsort(jacc_mat[idx])[-5:][::-1].tolist()
            elif use_method == "cosine_lsh":
                cands = list(cosine_lsh_candidates.get(idx, set()))
                if len(cands) >= 5:
                    top5 = sorted(cands, key=lambda j: float(cos_matrix[idx, j]), reverse=True)[:5]
                else:
                    top5 = np.argsort(cos_matrix[idx])[-5:][::-1].tolist()
            else:
                # 5 uploaders aleatorios
                pool = [k for k in range(n) if k != idx]
                top5 = rng.choice(pool, size=5, replace=False).tolist()
            rates.append(statistics.mean(uploaders[j]["flagged_frac"] for j in top5))
        return rates

    mh_flagged_rates = _top5_neighbor_flag_rates(flagged_idxs, "minhash_lsh")
    cos_flagged_rates = _top5_neighbor_flag_rates(flagged_idxs, "cosine_lsh")
    mh_unflagged_rates = _top5_neighbor_flag_rates(unflagged_idxs, "minhash_lsh")
    cos_unflagged_rates = _top5_neighbor_flag_rates(unflagged_idxs, "cosine_lsh")
    rand_baseline_rates = _top5_neighbor_flag_rates(flagged_idxs, "random")

    # Estadístico z (Welch) comparando vecinos MinHash de cuentas marcadas vs 5 uploaders aleatorios
    mu_mh = statistics.mean(mh_flagged_rates)
    mu_rand = statistics.mean(rand_baseline_rates)
    sd_mh = statistics.pstdev(mh_flagged_rates) or 1e-6
    sd_rand = statistics.pstdev(rand_baseline_rates) or 1e-6
    se = math.sqrt((sd_mh ** 2) / len(mh_flagged_rates) + (sd_rand ** 2) / len(rand_baseline_rates))
    z_stat = (mu_mh - mu_rand) / se if se > 0 else 0.0
    p_value = math.erfc(abs(z_stat) / math.sqrt(2.0))

    # Proporción de vecinos marcados (>= 0.25) para cuentas marcadas vs aleatorios
    def _frac_neighbors_flagged(indices: list[int], use_method: str) -> float:
        hits, total = 0, 0
        for idx in indices:
            if use_method == "minhash_lsh":
                cands = list(mh_adj.get(idx, set()))
                top5 = (
                    sorted(cands, key=lambda j: float(jacc_mat[idx, j]), reverse=True)[:5]
                    if len(cands) >= 5
                    else np.argsort(jacc_mat[idx])[-5:][::-1].tolist()
                )
            elif use_method == "cosine_lsh":
                cands = list(cosine_lsh_candidates.get(idx, set()))
                top5 = (
                    sorted(cands, key=lambda j: float(cos_matrix[idx, j]), reverse=True)[:5]
                    if len(cands) >= 5
                    else np.argsort(cos_matrix[idx])[-5:][::-1].tolist()
                )
            else:
                top5 = rng.choice([k for k in range(n) if k != idx], size=5, replace=False).tolist()
            hits += sum(1 for j in top5 if uploaders[j]["flagged_frac"] >= flagged_threshold)
            total += len(top5)
        return hits / total if total else 0.0

    outcome_groups = [
        {
            "group": "Cuentas marcadas → Top-5 MinHash/LSH",
            "short_label": "Flagged · MinHash",
            "mean_neighbor_flagged_frac": mu_mh,
            "pct_neighbors_flagged": _frac_neighbors_flagged(flagged_idxs, "minhash_lsh"),
            "lift_vs_random": mu_mh / mu_rand if mu_rand > 0 else 0.0,
            "sample_accounts": len(flagged_idxs),
        },
        {
            "group": "Cuentas marcadas → Top-5 Cosine LSH",
            "short_label": "Flagged · Cosine",
            "mean_neighbor_flagged_frac": statistics.mean(cos_flagged_rates),
            "pct_neighbors_flagged": _frac_neighbors_flagged(flagged_idxs, "cosine_lsh"),
            "lift_vs_random": statistics.mean(cos_flagged_rates) / mu_rand if mu_rand > 0 else 0.0,
            "sample_accounts": len(flagged_idxs),
        },
        {
            "group": "Cuentas normales → Top-5 MinHash/LSH",
            "short_label": "Normal · MinHash",
            "mean_neighbor_flagged_frac": statistics.mean(mh_unflagged_rates),
            "pct_neighbors_flagged": _frac_neighbors_flagged(unflagged_idxs, "minhash_lsh"),
            "lift_vs_random": statistics.mean(mh_unflagged_rates) / mu_rand if mu_rand > 0 else 0.0,
            "sample_accounts": len(unflagged_idxs),
        },
        {
            "group": "Baseline → 5 Uploaders Aleatorios",
            "short_label": "5 Aleatorios",
            "mean_neighbor_flagged_frac": mu_rand,
            "pct_neighbors_flagged": _frac_neighbors_flagged(flagged_idxs, "random"),
            "lift_vs_random": 1.0,
            "sample_accounts": len(flagged_idxs),
        },
    ]

    return {
        "queries_count": len(query_records),
        "mean_overlap_at_5": {
            "minhash_vs_cosine": statistics.mean(ov_mh_cos),
            "minhash_vs_lcs": statistics.mean(ov_mh_lcs),
            "cosine_vs_lcs": statistics.mean(ov_cos_lcs),
        },
        "disagreement_explanation": (
            "MinHash/LSH sobre 3-shingles detecta cuentas que comparten exactamente los mismos patrones "
            "consecutivos de transición de categorías (anillos coordinados de drift). Cosine LSH sobre el "
            "vector de ocupación captura perfiles con proporciones globales y volumen/vistas similares sin "
            "exigir el mismo orden secuencial. Unit 5 LCS preserva el orden global permitiendo inserciones "
            "intermedias, por lo que coincide más con MinHash en anillos coordinados pero tolera ruido puntual."
        ),
        "queries": query_records,
        "outcome_test": {
            "flagged_threshold": flagged_threshold,
            "flagged_accounts_count": len(flagged_idxs),
            "unflagged_accounts_count": len(unflagged_idxs),
            "excluded_from_vector": True,
            "minhash_lift_vs_random": mu_mh / mu_rand if mu_rand > 0 else 0.0,
            "cosine_lift_vs_random": statistics.mean(cos_flagged_rates) / mu_rand if mu_rand > 0 else 0.0,
            "z_statistic": z_stat,
            "p_value": p_value,
            "significant": p_value < 0.001,
            "groups": outcome_groups,
        },
    }


# --------------------------------------------------------------------------- #
# Orquestación completa del Workshop 5
# --------------------------------------------------------------------------- #
def run_workshop5(edges_w3_df: pd.DataFrame, seed: int = 42) -> dict[str, Any]:
    """Ejecuta todas las tareas del Workshop 5, persiste uploaders_workshop5_equipo4.json y retorna payload."""
    uploaders = generate_uploaders_dataset(edges_w3_df, n_uploaders=1_000, members_per_cluster=12, seed=seed)
    vectors = build_occupancy_vectors(uploaders)

    # Task 3 (S21): k = 2, 3, 4 shingles
    s21_shingles, shingles_k3 = analyze_k_shingles(uploaders, seed=seed)

    # Task 1: Distribuciones (5 000 pares), correlaciones (500 pares con LCS), concentración
    task1_repr = analyze_representations_and_distances(uploaders, shingles_k3, vectors, seed=seed)

    # Seleccionar 24 queries representativos (14 de anillos coordinados marcados + 4 de redes benignas + 6 de fondo)
    query_indices: list[int] = []
    seen_clusters: dict[str, int] = defaultdict(int)
    for idx, u in enumerate(uploaders):
        cid = u["_cluster_id"]
        if cid is not None and seen_clusters[cid] < 2 and len(query_indices) < 18:
            query_indices.append(idx)
            seen_clusters[cid] += 1
    for idx, u in enumerate(uploaders):
        if u["_cluster_id"] is None and len(query_indices) < 24:
            query_indices.append(idx)

    # Task 2: Random Hyperplanes (n=16, 32, 64, 128) + Cosine LSH
    task2_hyperplanes, cosine_lsh_cands, cos_matrix = analyze_random_hyperplanes(
        vectors, query_indices=query_indices, seed=seed
    )

    # Task 4 (S25): MinHash n=100 en MapReduceRunner (U4) + Diseño de umbral (b=20, r=5)
    s25_lsh, signatures, candidate_pairs, _ = run_minhash_lsh_mapreduce(
        uploaders,
        shingles_k3,
        n_hashes=100,
        bands=20,
        rows_per_band=5,
        s_threshold=0.6,
        num_workers=4,
        num_reducers=4,
        seed=seed,
    )

    # Extraer helpers internos antes de serializar
    top5_all = s25_lsh.pop("_top5_all")
    jacc_mat = s25_lsh.pop("_jacc_mat")

    # Task 5: Top-5 Neighbors en 24 queries + Outcome Test sobre flagged_frac
    task5_neighbors = analyze_neighbors_and_outcome_test(
        uploaders=uploaders,
        shingles_k3=shingles_k3,
        candidate_pairs=candidate_pairs,
        jacc_mat=jacc_mat,
        cosine_lsh_candidates=cosine_lsh_cands,
        cos_matrix=cos_matrix,
        query_indices=query_indices,
        seed=seed,
    )

    # Persistir dataset JSON oficial de Unidad 5 (template exacto del Excel)
    export_rows = []
    for i, u in enumerate(uploaders):
        export_rows.append({
            "uploader_id": u["uploader_id"],
            "category_sequence": u["category_sequence"],
            "seq_length": u["seq_length"],
            "flagged_frac": u["flagged_frac"],
            "avg_view_count_1h": u["avg_view_count_1h"],
            "shingle_count": len(shingles_k3[i]),
            "minhash_signature": signatures[u["uploader_id"]],
            "occupancy_vector": [round(float(x), 4) for x in vectors[i]],
            "neighbors": top5_all[i],
        })
    UPLOADERS_W5.parent.mkdir(parents=True, exist_ok=True)
    UPLOADERS_W5.write_text(json.dumps(export_rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    return {
        "meta": {
            "n_uploaders": len(uploaders),
            "planted_clusters": len(PLANTED_CLUSTERS),
            "malicious_clusters": sum(1 for c in PLANTED_CLUSTERS if c["malicious"]),
            "planted_accounts": sum(1 for u in uploaders if u["_is_planted"]),
            "background_accounts": sum(1 for u in uploaders if not u["_is_planted"]),
            "dataset_file": UPLOADERS_W5.name,
        },
        "task1_representations": task1_repr,
        "task2_hyperplanes": task2_hyperplanes,
        "task3_k_shingles": s21_shingles,
        "task4_threshold_lsh": s25_lsh,
        "task5_neighbors_outcome": task5_neighbors,
    }

