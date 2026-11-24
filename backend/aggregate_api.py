"""API del dashboard: GET /api/dashboard devuelve un único JSON con los 4 paneles.

Compatible tanto con ejecución directa:
    py backend/aggregate_api.py --serve 8000
Como con servidores WSGI de producción (Render, Gunicorn):
    gunicorn backend.aggregate_api:app --bind 0.0.0.0:$PORT
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics_and_graphs as mg  # noqa: E402
from static_results import load_static  # noqa: E402
from streaming import StreamEngine  # noqa: E402


class Dashboard:
    """Une los resultados estáticos con el estado en vivo del stream."""

    def __init__(self, refresh: bool = False, rate_eps: float = 25.0):
        self.static = load_static(refresh)
        self.engine = StreamEngine(mg.load_stream(), rate_eps)

    def payload(self, pos: int | None = None) -> dict:
        s, live = self.static, self.engine.snapshot(pos)
        w4 = s["workshop4"]
        w5 = s["workshop5"]
        return {
            "meta": {**s["meta"], "generated_at": datetime.now(timezone.utc).isoformat()},
            "capacity": s["capacity"],
            "panel_a_bucket_load": s["hashing"],
            "panel_b_runtimes": s["quicksort"],
            "panel_c_realtime": {
                "live": live,
                "bloom_final": s["bloom_final"],
                "hll_by_day": s["hll_by_day"],
                "reservoir_view_count": s["reservoir_view_count"],
                "chernoff": s["chernoff"],
                "moments_overall": s["moments_overall"],
            },
            "panel_d_pagerank": {**s["pagerank"], "markov": s["markov"]},
            "panel_e_mapreduce": {
                "pipeline_validation": w4["pipeline_validation"],
                "s10_pagerank_mr": w4["s10_pagerank_mr"],
                "cost_analysis": w4["cost_analysis"],
                "reducer_analysis": w4["reducer_analysis"],
                "s14_skew_mitigation": w4["s14_skew_mitigation"],
            },
            "panel_f_category_flow": {
                "node_summary_100k": w4["node_summary_100k"],
                "node_summary_unit3": w4["node_summary_unit3"],
                "mean_flagged_frac": w4["mean_flagged_frac"],
                "unit3_edge_validation": w4["pipeline_validation"]["unit3_edge_validation"],
                "s10_pagerank_mr": w4["s10_pagerank_mr"],
            },
            "panel_g_neighbors": {
                "meta": w5["meta"],
                "task1_representations": w5["task1_representations"],
                "task2_hyperplanes": w5["task2_hyperplanes"],
                "task3_k_shingles": w5["task3_k_shingles"],
                "queries_count": w5["task5_neighbors_outcome"]["queries_count"],
                "mean_overlap_at_5": w5["task5_neighbors_outcome"]["mean_overlap_at_5"],
                "disagreement_explanation": w5["task5_neighbors_outcome"]["disagreement_explanation"],
                "queries": w5["task5_neighbors_outcome"]["queries"],
            },
            "panel_h_threshold_outcome": {
                "meta": w5["meta"],
                "threshold_lsh": w5["task4_threshold_lsh"],
                "outcome_test": w5["task5_neighbors_outcome"]["outcome_test"],
            },
        }


# Instancia singleton perezosa para WSGI / Standalone (evita recálculo en workers Windows)
_dash_singleton: Dashboard | None = None


def get_dashboard(refresh: bool = False, rate_eps: float = 25.0) -> Dashboard:
    global _dash_singleton
    if refresh or _dash_singleton is None:
        _dash_singleton = Dashboard(refresh=refresh, rate_eps=rate_eps)
    return _dash_singleton


def app(environ, start_response):
    """Aplicación WSGI estándar compatible con Gunicorn / uWSGI / Render."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/").rstrip("/") or "/"

    headers = [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]

    print(f"[API] {method} {path}", flush=True)

    if method == "OPTIONS":
        start_response("204 No Content", headers)
        return [b""]

    if path in ("/", "/health") or path.endswith("/health"):
        data = json.dumps({"status": "ok", "service": "content-moderation-api"}).encode("utf-8")
        headers.extend([("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(data)))])
        start_response("200 OK", headers)
        return [] if method == "HEAD" else [data]

    if path in ("/api/dashboard", "/dashboard", "/api") or path.endswith("/dashboard"):
        try:
            qs = parse_qs(environ.get("QUERY_STRING", ""))
            pos = int(qs["pos"][0]) if "pos" in qs else None
            data = json.dumps(get_dashboard().payload(pos), ensure_ascii=False).encode("utf-8")
            headers.extend([("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(data)))])
            start_response("200 OK", headers)
            return [] if method == "HEAD" else [data]
        except Exception as e:
            print(f"[API ERROR] {e}", flush=True)
            import traceback
            traceback.print_exc()
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [f"Internal Error: {e}".encode("utf-8")]

    print(f"[API 404] Path not matched: {path}", flush=True)
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


def make_handler(dash: Dashboard):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/health"):
                body = json.dumps({"status": "ok", "service": "content-moderation-api"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self._cors()
                self.end_headers()
                self.wfile.write(body)
                return
            if url.path != "/api/dashboard":
                self.send_error(404)
                return
            q = parse_qs(url.query)
            pos = int(q["pos"][0]) if "pos" in q else None
            body = json.dumps(dash.payload(pos), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            try:
                self.wfile.write(body)
            except (ConnectionAbortedError, BrokenPipeError):
                pass

        def log_message(self, *args):
            pass

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serve", type=int, metavar="PORT", help="levanta GET /api/dashboard")
    ap.add_argument("--refresh", action="store_true", help="recalcula los resultados estáticos")
    ap.add_argument("--rate", type=float, default=25.0, help="eventos/s simulados del stream")
    args = ap.parse_args()

    dash = get_dashboard(refresh=args.refresh, rate_eps=args.rate)

    port = args.serve or (int(os.environ["PORT"]) if "PORT" in os.environ else None)
    if port:
        print(f"API lista: http://0.0.0.0:{port}/api/dashboard", flush=True)
        ThreadingHTTPServer(("0.0.0.0", port), make_handler(dash)).serve_forever()
    else:
        print(json.dumps(dash.payload(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
