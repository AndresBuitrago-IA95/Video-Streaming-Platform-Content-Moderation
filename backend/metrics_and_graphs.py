"""Motor analítico del dashboard integrado (Workshops 1-3, Equipo 4).

Consume los datos ya existentes en el workspace y calcula:
  1. Cotas de Chernoff sobre la tasa de videos marcados por uploader.
  2. Momentos de frecuencia exactos F0, F1, F2 sobre categorías (global y por ventana).
  3. PageRank estándar sobre la matriz de transición de categorías, comparado
     contra el ranking por frecuencia de subidas.

Dependencias: pandas, numpy.   Uso:  py metrics_and_graphs.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from config import TRANSITIONS_W3, VIDEOS_W1, VIDEOS_W2  # noqa: E402  (datos dentro del repo)


# --------------------------------------------------------------------------- #
# Carga de datos
# --------------------------------------------------------------------------- #
def load_videos(path: Path = VIDEOS_W1) -> pd.DataFrame:
    """Videos del Workshop 1 (10 000 registros, orden arbitrario)."""
    df = pd.read_json(path, encoding="utf-8", dtype={"uploader_id": str, "video_id": str})
    df["upload_time"] = pd.to_datetime(df["upload_time"])
    df["is_flagged"] = df["is_flagged"].astype(bool)
    return df


def load_stream(path: Path = VIDEOS_W2) -> pd.DataFrame:
    """Flujo ordenado del Workshop 2 (campo stream_seq), base de las consultas streaming."""
    df = pd.read_json(path, encoding="utf-8", dtype={"uploader_id": str, "video_id": str})
    df["upload_time"] = pd.to_datetime(df["upload_time"])
    df["is_flagged"] = df["is_flagged"].astype(bool)
    return df.sort_values("stream_seq").reset_index(drop=True)


def load_transitions(path: Path = TRANSITIONS_W3) -> pd.DataFrame:
    return pd.read_json(path, encoding="utf-8")


def build_transition_matrix(edges: pd.DataFrame) -> pd.DataFrame:
    """Matriz estocástica por filas P[i, j] = conteo(i->j) / sum_j conteo(i->j)."""
    counts = edges.pivot_table(index="from_category", columns="to_category",
                               values="transition_count", aggfunc="sum", fill_value=0.0)
    cats = sorted(set(counts.index) | set(counts.columns))
    counts = counts.reindex(index=cats, columns=cats, fill_value=0.0).astype(float)
    totals = counts.sum(axis=1)
    P = counts.div(totals.replace(0, np.nan), axis=0)
    # Estados sin salidas (dangling): fila uniforme, convención estándar de PageRank
    P = P.apply(lambda row: row.fillna(1.0 / len(cats)) if row.isna().all() else row.fillna(0.0),
                axis=1)
    return P


# --------------------------------------------------------------------------- #
# 1. Cotas de Chernoff
# --------------------------------------------------------------------------- #
def chernoff_upper_tail(n: int, p0: float, k: int) -> float:
    """Cota de Chernoff (forma de entropía relativa) para P[Bin(n, p0) >= k].

        P[X >= k] <= exp(-n * KL(k/n || p0))      si k/n > p0
                  <= 1                              en otro caso

    Es la versión más ajustada de la cota multiplicativa
    (e^d / (1+d)^(1+d))^mu con mu = n*p0 y 1+d = k/(n*p0).
    """
    if n <= 0 or k <= n * p0:
        return 1.0
    if p0 <= 0.0:
        return 0.0
    q = k / n
    kl = q * math.log(q / p0)
    if q < 1.0:
        kl += (1 - q) * math.log((1 - q) / (1 - p0))
    return math.exp(-n * kl)


def chernoff_uploader_analysis(
    videos: pd.DataFrame,
    threshold_rate: float | None = None,
    alpha: float = 0.01,
    min_videos: int = 5,
) -> tuple[pd.DataFrame, dict]:
    """Evalúa si la tasa de videos marcados de cada uploader supera un umbral sospechoso.

    Modelo nulo: cada video de un uploader se marca con la tasa base global p0.
    - threshold_rate: tasa a partir de la cual se considera sospechoso (por defecto 2*p0).
    - chernoff_p_observed: cota sobre P[X >= k_obs | uploader honesto]. Si < alpha,
      el exceso es estadísticamente improbable bajo el modelo nulo.
    - chernoff_p_threshold: cota sobre P[tasa >= umbral | uploader honesto] para ese n.
    Un uploader es 'suspicious' si rate > umbral Y la cota observada < alpha.
    """
    p0 = float(videos["is_flagged"].mean())
    thr = threshold_rate if threshold_rate is not None else min(2 * p0, 0.99)

    g = videos.groupby("uploader_id")["is_flagged"].agg(videos="size", flagged="sum").reset_index()
    g = g[g["videos"] >= min_videos].copy()
    g["flag_rate"] = g["flagged"] / g["videos"]
    g["expected_flagged"] = g["videos"] * p0
    g["exceeds_threshold"] = g["flag_rate"] > thr
    g["chernoff_p_observed"] = [chernoff_upper_tail(int(n), p0, int(k))
                                for n, k in zip(g["videos"], g["flagged"])]
    g["chernoff_p_threshold"] = [chernoff_upper_tail(int(n), p0, math.ceil(thr * n))
                                 for n in g["videos"]]
    g["suspicious"] = g["exceeds_threshold"] & (g["chernoff_p_observed"] < alpha)
    g = g.sort_values(["suspicious", "chernoff_p_observed", "flag_rate"],
                      ascending=[False, True, False]).reset_index(drop=True)

    summary = {
        "baseline_flag_rate": p0,
        "threshold_rate": thr,
        "alpha": alpha,
        "min_videos": min_videos,
        "uploaders_evaluated": int(len(g)),
        "uploaders_exceeding_threshold": int(g["exceeds_threshold"].sum()),
        "uploaders_suspicious": int(g["suspicious"].sum()),
    }
    return g, summary


# --------------------------------------------------------------------------- #
# 2. Momentos de frecuencia F0, F1, F2
# --------------------------------------------------------------------------- #
def frequency_moments(items: pd.Series) -> dict:
    """Momentos exactos: F0 = #distintos, F1 = #elementos, F2 = suma de f_i^2."""
    f = items.value_counts()
    f0, f1, f2 = int(len(f)), int(f.sum()), int((f.astype("int64") ** 2).sum())
    return {
        "F0": f0,
        "F1": f1,
        "F2": f2,
        # F2/F1^2 = probabilidad de colisión: 1/F0 si uniforme, 1 si todo es una categoría
        "collision_prob": f2 / f1 ** 2 if f1 else 0.0,
        "uniform_baseline": 1 / f0 if f0 else 0.0,
        "skew_ratio": (f2 / f1 ** 2) * f0 if f1 and f0 else 0.0,  # 1 = uniforme
        "top_category": f.index[0] if f0 else None,
        "top_share": float(f.iloc[0] / f1) if f1 else 0.0,
    }


def category_moments(videos: pd.DataFrame) -> dict:
    """F_k globales y solo sobre videos marcados (los spam suelen concentrarse)."""
    return {
        "all_videos": frequency_moments(videos["category"]),
        "flagged_videos": frequency_moments(videos.loc[videos["is_flagged"], "category"]),
    }


def windowed_moments(stream: pd.DataFrame, window: int = 250, z_threshold: float = 2.0
                     ) -> pd.DataFrame:
    """F0/F1/F2 por ventana del flujo; una ola de spam eleva F2 (concentración) y/o la
    tasa de marcados. Se marca la ventana si el z-score de F2 o de flagged_rate > umbral."""
    rows = []
    for w, start in enumerate(range(0, len(stream), window)):
        chunk = stream.iloc[start:start + window]
        if len(chunk) < window // 2:  # ventana final demasiado corta -> ruido
            continue
        m = frequency_moments(chunk["category"])
        rows.append({
            "window": w, "start_seq": int(chunk["stream_seq"].iloc[0]),
            "end_seq": int(chunk["stream_seq"].iloc[-1]),
            "F0": m["F0"], "F1": m["F1"], "F2": m["F2"],
            "skew_ratio": m["skew_ratio"], "top_category": m["top_category"],
            "flagged_rate": float(chunk["is_flagged"].mean()),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ("F2", "flagged_rate"):
        sd = df[col].std(ddof=0)
        df[f"z_{col}"] = (df[col] - df[col].mean()) / sd if sd > 0 else 0.0
    df["spam_wave"] = (df["z_F2"] > z_threshold) | (df["z_flagged_rate"] > z_threshold)
    return df


def flagged_rate_by_category(videos: pd.DataFrame) -> pd.DataFrame:
    g = videos.groupby("category")["is_flagged"].agg(videos="size", flagged="sum").reset_index()
    g["flag_rate"] = g["flagged"] / g["videos"]
    return g.sort_values("flag_rate", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 3. PageRank vs ranking por frecuencia
# --------------------------------------------------------------------------- #
def pagerank(P: pd.DataFrame, damping: float = 0.85, tol: float = 1e-12,
             max_iter: int = 1000) -> tuple[pd.Series, int]:
    """PageRank estándar por iteración de potencia:  r <- d * P^T r + (1-d)/N."""
    M = P.to_numpy(dtype=float)
    n = M.shape[0]
    r = np.full(n, 1.0 / n)
    for it in range(1, max_iter + 1):
        new = damping * (M.T @ r) + (1 - damping) / n
        new /= new.sum()
        if np.abs(new - r).sum() < tol:
            r = new
            break
        r = new
    return pd.Series(r, index=P.index, name="pagerank"), it


def pagerank_vs_frequency(videos: pd.DataFrame, P: pd.DataFrame,
                          damping: float = 0.85) -> tuple[pd.DataFrame, dict]:
    """DataFrame que compara el score PageRank con el ranking por frecuencia de subidas."""
    pr, iters = pagerank(P, damping)
    freq = videos["category"].value_counts().rename("upload_count")
    df = pd.concat([pr, freq], axis=1).reindex(P.index).fillna(0).reset_index()
    df.columns = ["category", "pagerank", "upload_count"]
    df["upload_count"] = df["upload_count"].astype(int)
    df["freq_share"] = df["upload_count"] / df["upload_count"].sum()
    df["pagerank_rank"] = df["pagerank"].rank(ascending=False, method="min").astype(int)
    df["frequency_rank"] = df["upload_count"].rank(ascending=False, method="min").astype(int)
    df["rank_delta"] = df["frequency_rank"] - df["pagerank_rank"]  # >0: PR lo sube
    # Escalas comparables (0-100) para el radar / barras compuestas
    for col, out in (("pagerank", "pagerank_scaled"), ("freq_share", "frequency_scaled")):
        lo, hi = df[col].min(), df[col].max()
        df[out] = 100 * (df[col] - lo) / (hi - lo) if hi > lo else 50.0
    df = df.sort_values("pagerank_rank").reset_index(drop=True)

    # Spearman = Pearson sobre rangos (evita depender de scipy)
    rho = df["pagerank_rank"].corr(df["frequency_rank"])
    meta = {"damping": damping, "iterations": iters,
            "spearman_rank_correlation": None if pd.isna(rho) else float(rho),
            "pagerank_spread": float(df["pagerank"].max() - df["pagerank"].min())}
    return df, meta


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #
def run_all(threshold_rate: float | None = None, window: int = 250) -> dict:
    videos = load_videos()
    stream = load_stream()
    P = build_transition_matrix(load_transitions())

    uploaders, chernoff_meta = chernoff_uploader_analysis(videos, threshold_rate)
    pr_df, pr_meta = pagerank_vs_frequency(videos, P)
    return {
        "videos": videos,
        "stream": stream,
        "transition_matrix": P,
        "chernoff_uploaders": uploaders,
        "chernoff_summary": chernoff_meta,
        "moments": category_moments(videos),
        "moments_windowed": windowed_moments(stream, window),
        "flag_rate_by_category": flagged_rate_by_category(videos),
        "pagerank": pr_df,
        "pagerank_meta": pr_meta,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threshold", type=float, default=None,
                    help="tasa sospechosa (default: 2x la tasa base)")
    ap.add_argument("--window", type=int, default=250, help="tamaño de ventana del flujo")
    ap.add_argument("--out", type=Path, default=None, help="directorio para guardar CSV/JSON")
    args = ap.parse_args()

    res = run_all(args.threshold, args.window)
    pd.set_option("display.width", 160, "display.max_columns", 20)

    print("== Chernoff ==")
    print(json.dumps(res["chernoff_summary"], indent=2))
    print(res["chernoff_uploaders"].head(10).to_string(index=False))
    print("\n== Momentos de frecuencia ==")
    print(json.dumps(res["moments"], indent=2, ensure_ascii=False, default=str))
    waves = res["moments_windowed"]
    print(f"\nVentanas del flujo: {len(waves)} | olas de spam detectadas: "
          f"{int(waves['spam_wave'].sum()) if len(waves) else 0}")
    print("\n== PageRank vs frecuencia ==")
    print(json.dumps(res["pagerank_meta"], indent=2))
    print(res["pagerank"].round(5).to_string(index=False))

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        res["chernoff_uploaders"].to_csv(args.out / "chernoff_uploaders.csv", index=False)
        res["moments_windowed"].to_csv(args.out / "moments_windowed.csv", index=False)
        res["pagerank"].to_csv(args.out / "pagerank_vs_frequency.csv", index=False)
        res["flag_rate_by_category"].to_csv(args.out / "flag_rate_by_category.csv", index=False)
        print(f"\nGuardado en {args.out}")


if __name__ == "__main__":
    main()
