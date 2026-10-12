"""Capa de agregación de datos / API del dashboard integrado.

Reúne en un único JSON:
  - Juan Camilo: tasas de falsos positivos del Bloom filter, tiempos de QuickSort,
    carga de buckets (chaining vs. power of two choices).
  - Arley: consultas streaming (tasa de marcados, flujo, reservoir sampling).
  - Motor analítico (metrics_and_graphs.py): Chernoff, F0/F1/F2, PageRank.

Uso:
    py aggregate_api.py                 # escribe ../output/dashboard_data.json (+ copia a la app si existe)
    py aggregate_api.py --serve 8000    # sirve GET http://localhost:8000/api/dashboard
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import datetime, timezone
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

import metrics_and_graphs as mg

WORKSPACE = mg.WORKSPACE
DASH_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = DASH_ROOT / "output" / "dashboard_data.json"
FRONTEND_PUBLIC = DASH_ROOT / "frontend" / "public" / "data" / "dashboard_data.json"

JC_W1 = WORKSPACE / "Workshop1_Entrega_Final_Juan_Camilo"
JC_W2 = WORKSPACE / "Workshop2_Entrega_Final_Juan_Camilo"
ARLEY_W2 = WORKSPACE / "Equipo_4_logica_3_w2"
ARLEY_W1 = WORKSPACE / "Equipo_4_logica_3"

HASH_CONFIGS = [(1000, 128), (1000, 512), (1000, 1024), (5000, 128), (5000, 512),
                (5000, 1024), (10000, 128), (10000, 512), (10000, 1024)]


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _clean(obj):
    """Hace el objeto serializable: NaN/inf -> None, numpy -> tipos nativos."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if hasattr(obj, "item"):
        obj = obj.item()
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _frame(df: pd.DataFrame) -> list[dict]:
    return _clean(df.to_dict(orient="records"))


def _load_juan_w1():
    """Reutiliza bucket_loads() de Juan Camilo para que la distribución sea idéntica a la suya."""
    spec = importlib.util.spec_from_file_location("jc_w1", JC_W1 / "workshop1_juan_camilo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Panel A — distribución de carga por bucket
# --------------------------------------------------------------------------- #
def bucket_load_panel(videos: pd.DataFrame) -> dict:
    jc = _load_juan_w1()
    ids = (videos["uploader_id"].astype(str) + ":" + videos["video_id"].astype(str)).tolist()
    summary = _read_csv(JC_W1 / "resultados" / "hashing_comparacion.csv")

    configs = {}
    for n, buckets in HASH_CONFIGS:
        loads = {m: jc.bucket_loads(ids[:n], buckets, m) for m in ("chaining", "two_choices")}
        max_load = max(max(v) for v in loads.values())
        rows = []
        for load in range(max_load + 1):
            rows.append({"load": load,
                         "chaining": loads["chaining"].count(load),
                         "two_choices": loads["two_choices"].count(load)})
        stats = summary[(summary.n == n) & (summary.buckets == buckets)]
        configs[f"{n}_{buckets}"] = {
            "n": n, "buckets": buckets, "histogram": rows,
            "stats": {r.metodo: {"max_load": int(r.carga_maxima), "mean": float(r.carga_media),
                                 "std": float(r.desviacion_estandar),
                                 "empty_buckets": int(r.buckets_vacios)}
                      for r in stats.itertuples()},
        }
    return {"default_config": "10000_512", "configs": configs}


# --------------------------------------------------------------------------- #
# Panel B — QuickSort determinista vs. aleatorizado
# --------------------------------------------------------------------------- #
def quicksort_panel() -> dict:
    df = _read_csv(JC_W1 / "resultados" / "quicksort_comparacion.csv")
    out = {}
    for scenario, g in df.groupby("escenario"):
        wide = g.pivot(index="n", columns="algoritmo", values="tiempo_promedio_ms").reset_index()
        out[scenario] = [{"n": int(r.n), "deterministic_ms": float(r.determinista),
                          "randomized_ms": float(r.aleatorizado)} for r in wide.itertuples()]
    worst = df[(df.escenario == "ordenado") & (df.n == df.n.max())].set_index("algoritmo")
    speedup = float(worst.loc["determinista", "tiempo_promedio_ms"]
                    / worst.loc["aleatorizado", "tiempo_promedio_ms"])
    return {"scenarios": out, "default_scenario": "ordenado",
            "worst_case_speedup": speedup, "unit": "ms"}


# --------------------------------------------------------------------------- #
# Bloom filter y consultas streaming (Panel C)
# --------------------------------------------------------------------------- #
def bloom_panel() -> dict:
    df = _read_csv(JC_W2 / "resultados" / "bloom_comparacion.csv")
    rows = [{"bits_per_element": int(r.bits_por_elemento), "hash_functions": int(r.funciones_hash),
             "false_positives": int(r.falsos_positivos), "negatives": int(r.negativos_evaluados),
             "fp_rate_experimental": float(r.tasa_falsos_positivos_experimental),
             "fp_rate_theoretical": float(r.tasa_falsos_positivos_teorica),
             "false_negatives": int(r.falsos_negativos)} for r in df.itertuples()]
    return {"configs": rows, "highlight_bits_per_element": 8}


def streaming_panel(stream: pd.DataFrame, windowed: pd.DataFrame) -> dict:
    """Consultas streaming de Arley: estado acumulado del flujo, ventanas y reservoir sampling."""
    jsonl = ARLEY_W1 / "videos_stream_equipo4.jsonl"
    live = pd.read_json(jsonl, lines=True, encoding="utf-8") if jsonl.exists() else pd.DataFrame()
    reservoir = _read_csv(ARLEY_W2 / "resultados_reservoir_equipo4.csv")
    best = reservoir[reservoir.tamano_muestra == reservoir.tamano_muestra.max()]
    return {
        "stream_events": int(len(stream)),
        "stream_flagged_rate": float(stream["is_flagged"].mean()),
        "recent_window_flagged_rate": float(stream.tail(250)["is_flagged"].mean()),
        "live_feed_events": int(len(live)),
        "live_feed_flagged": int(live["is_flagged"].sum()) if len(live) else 0,
        "windows": _frame(windowed[["window", "start_seq", "end_seq", "F0", "F1", "F2",
                                    "flagged_rate", "spam_wave"]]) if len(windowed) else [],
        "reservoir_mean_duration": _frame(best[["categoria", "promedio_exacto",
                                                "promedio_estimado", "error_porcentual"]]),
        "reservoir_sample_size": int(reservoir.tamano_muestra.max()),
    }


# --------------------------------------------------------------------------- #
# Ensamblado final
# --------------------------------------------------------------------------- #
def build_payload() -> dict:
    res = mg.run_all()
    videos = res["videos"]
    uploaders = res["chernoff_uploaders"]
    suspicious = uploaders[uploaders["suspicious"]].head(10)
    top = suspicious if len(suspicious) else uploaders.head(10)

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "videos": int(len(videos)),
            "categories": int(videos["category"].nunique()),
            "sources": {"arley": ["Equipo_4_logica_3", "Equipo_4_logica_3_w2",
                                  "Equipo_4_logica_3_w3"],
                        "juan_camilo": ["Workshop1_Entrega_Final_Juan_Camilo",
                                        "Workshop2_Entrega_Final_Juan_Camilo",
                                        "Workshop3_Entrega_Final_Juan_Camilo"]},
        },
        "panel_a_bucket_load": bucket_load_panel(videos),
        "panel_b_runtimes": quicksort_panel(),
        "panel_c_realtime": {
            "flag_rate_by_category": _frame(res["flag_rate_by_category"]),
            "global_flag_rate": float(videos["is_flagged"].mean()),
            "frequency_moments": res["moments"],
            "bloom_filter": bloom_panel(),
            "chernoff": {"summary": res["chernoff_summary"],
                         "top_uploaders": _frame(top[["uploader_id", "videos", "flagged",
                                                      "flag_rate", "chernoff_p_observed",
                                                      "suspicious"]])},
            "streaming": streaming_panel(res["stream"], res["moments_windowed"]),
        },
        "panel_d_pagerank": {
            "meta": res["pagerank_meta"],
            "categories": _frame(res["pagerank"]),
        },
    }
    return _clean(payload)


def write_payload(payload: dict) -> list[Path]:
    written = []
    targets = [OUTPUT] + ([FRONTEND_PUBLIC] if FRONTEND_PUBLIC.parent.parent.exists() else [])
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)
    return written


CACHE_TTL_S = 5.0
_cache = {"t": 0.0, "body": b""}
_lock = threading.Lock()


def _cached_body() -> bytes:
    with _lock:
        if time.monotonic() - _cache["t"] > CACHE_TTL_S or not _cache["body"]:
            _cache["body"] = json.dumps(build_payload(), ensure_ascii=False).encode("utf-8")
            _cache["t"] = time.monotonic()
        return _cache["body"]


class _Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] != "/api/dashboard":
            self.send_error(404)
            return
        body = _cached_body()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serve", type=int, metavar="PORT", help="levanta GET /api/dashboard")
    args = ap.parse_args()
    if args.serve:
        print(f"Sirviendo http://localhost:{args.serve}/api/dashboard")
        ThreadingHTTPServer(("", args.serve), _Handler).serve_forever()
    else:
        for p in write_payload(build_payload()):
            print("Escrito:", p)


if __name__ == "__main__":
    main()
