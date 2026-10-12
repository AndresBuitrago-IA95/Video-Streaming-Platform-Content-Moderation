"""Motor de streaming (W2): simula la llegada continua de subidas y responde consultas.

- Consulta permanente: tasa de marcados por categoría en las últimas 1 000 subidas.
- F0/F1/F2 exactos sobre la ventana y detección de olas de spam (z-score de F2).
- Bloom filter de uploaders marcados y su tasa de falsos positivos «hasta ahora».
- Consulta ad-hoc: uploaders distintos hoy (exacto vs. HyperLogLog).

La posición del cursor avanza con el reloj (`rate_eps` eventos/s) y da la vuelta al llegar al final,
así cada petición de la API ve un estado distinto del flujo.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from algorithms.bloom import sized_filter
from algorithms.hashing import stable_hash
from algorithms.hyperloglog import HyperLogLog

WINDOW = 1000          # tamaño de la ventana móvil (consulta permanente de W2 T1)
STEP = 50              # resolución de la serie temporal
Z_ALERT = 2.0          # umbral de alerta de spam
BLOOM_BITS = (4, 8, 12, 16)
HLL_M = (16, 32, 64, 128)


class StreamEngine:
    def __init__(self, stream: pd.DataFrame, rate_eps: float = 25.0):
        self.df = stream.sort_values("stream_seq").reset_index(drop=True)
        self.n = len(self.df)
        self.rate = rate_eps
        self.t0 = time.monotonic()

        self.cats = sorted(self.df["category"].unique())
        cat_idx = self.df["category"].map({c: i for i, c in enumerate(self.cats)}).to_numpy()
        flagged = self.df["is_flagged"].to_numpy(bool)
        eye = np.eye(len(self.cats), dtype=np.int64)[cat_idx]
        self.cum_cat = np.vstack([np.zeros((1, len(self.cats)), np.int64), np.cumsum(eye, 0)])
        self.cum_flag = np.vstack([np.zeros((1, len(self.cats)), np.int64),
                                   np.cumsum(eye * flagged[:, None], 0)])
        self.flagged = flagged

        uploaders = self.df["uploader_id"].tolist()
        self.uploaders = uploaders
        self.hash64 = {u: stable_hash(u) for u in set(uploaders)}
        self.day = self.df["upload_time"].dt.normalize().to_numpy()
        # línea base para el z-score: todos los puntos de control de la serie
        self.checkpoints = list(range(WINDOW, self.n + 1, STEP))
        self._f2 = np.array([self._moments_at(p)[2] for p in self.checkpoints], float)
        self._rate = np.array([self._flag_rate_at(p) for p in self.checkpoints], float)
        self._f2_mu, self._f2_sd = self._f2.mean(), self._f2.std() or 1.0
        self._rate_mu, self._rate_sd = self._rate.mean(), self._rate.std() or 1.0

    # ------------------------------------------------------------------ #
    def position(self, override: int | None = None) -> int:
        if override is not None:
            return int(min(max(override, WINDOW), self.n))
        span = self.n - WINDOW + 1
        return WINDOW + int((time.monotonic() - self.t0) * self.rate) % span

    def _window_counts(self, p: int) -> np.ndarray:
        return self.cum_cat[p] - self.cum_cat[p - WINDOW]

    def _moments_at(self, p: int) -> tuple[int, int, int]:
        c = self._window_counts(p)
        return int((c > 0).sum()), int(c.sum()), int((c.astype(np.int64) ** 2).sum())

    def _flag_rate_at(self, p: int) -> float:
        return float((self.cum_flag[p] - self.cum_flag[p - WINDOW]).sum() / WINDOW)

    # ------------------------------------------------------------------ #
    def _bloom_live(self, p: int) -> list[dict]:
        flagged_users = {u for u, f in zip(self.uploaders[:p], self.flagged[:p]) if f}
        negatives = sorted(set(self.uploaders[:p]) - flagged_users)
        rows = []
        for bits in BLOOM_BITS:
            bf = sized_filter(len(flagged_users), bits)
            for u in flagged_users:
                bf.add(u)
            fp = sum(u in bf for u in negatives)
            rows.append({
                "bits_per_element": bits, "hash_functions": bf.hashes,
                "inserted": len(flagged_users), "negatives": len(negatives),
                "false_positives": fp,
                "false_negatives": sum(u not in bf for u in flagged_users),
                "fp_rate_experimental": fp / len(negatives) if negatives else 0.0,
                "fp_rate_theoretical": bf.theoretical_fp(),
            })
        return rows

    def _hll_today(self, p: int) -> dict:
        today = self.day[p - 1]
        users = [u for u, d in zip(self.uploaders[:p], self.day[:p]) if d == today]
        true = len(set(users))
        rows = []
        for m in HLL_M:
            h = HyperLogLog(m)
            for u in set(users):
                h.add_hash(self.hash64[u])
            est = h.estimate()
            rows.append({"m": m, "memory_bits": h.memory_bits, "estimate": est,
                         "rel_error": abs(est - true) / true if true else 0.0,
                         "theoretical_error": h.theoretical_error})
        return {"date": str(pd.Timestamp(today).date()), "true_distinct": true, "estimates": rows}

    # ------------------------------------------------------------------ #
    def snapshot(self, pos: int | None = None) -> dict:
        p = self.position(pos)
        counts = self._window_counts(p)
        flagged = self.cum_flag[p] - self.cum_flag[p - WINDOW]
        f0, f1, f2 = self._moments_at(p)
        z_f2 = (f2 - self._f2_mu) / self._f2_sd
        rate = self._flag_rate_at(p)
        z_rate = (rate - self._rate_mu) / self._rate_sd

        per_cat = [{"category": c, "videos": int(counts[i]), "flagged": int(flagged[i]),
                    "flag_rate": float(flagged[i] / counts[i]) if counts[i] else 0.0}
                   for i, c in enumerate(self.cats)]

        # momentos solo sobre los marcados de la ventana
        fl = flagged.astype(np.int64)
        flagged_moments = {"F0": int((fl > 0).sum()), "F1": int(fl.sum()), "F2": int((fl ** 2).sum())}
        top = int(np.argmax(counts))

        idx = [i for i, cp in enumerate(self.checkpoints) if cp <= p][-60:]
        series = [{"position": self.checkpoints[i], "F2": float(self._f2[i]),
                   "flag_rate": float(self._rate[i]),
                   "z_F2": float((self._f2[i] - self._f2_mu) / self._f2_sd),
                   "spam_wave": bool((self._f2[i] - self._f2_mu) / self._f2_sd > Z_ALERT
                                     or (self._rate[i] - self._rate_mu) / self._rate_sd > Z_ALERT)}
                  for i in idx]

        return {
            "position": p, "stream_length": self.n, "window": WINDOW, "events_per_second": self.rate,
            "rolling_flag_rate_by_category": per_cat,
            "overall_flag_rate": rate,
            "moments": {"F0": f0, "F1": f1, "F2": f2,
                        "collision_prob": f2 / f1 ** 2,
                        "uniform_baseline": 1 / len(self.cats),
                        "skew_ratio": f2 / f1 ** 2 * len(self.cats),
                        "top_category": self.cats[top], "top_share": float(counts[top] / f1)},
            "flagged_moments": flagged_moments,
            "spam": {"z_F2": float(z_f2), "z_flag_rate": float(z_rate), "threshold": Z_ALERT,
                     "alert": bool(z_f2 > Z_ALERT or z_rate > Z_ALERT)},
            "series": series,
            "bloom_live": self._bloom_live(p),
            "distinct_uploaders_today": self._hll_today(p),
        }
