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
        }


# Instancia singleton para WSGI / Standalone
dash_instance = Dashboard(refresh=False)


def app(environ, start_response):
    """Aplicación WSGI estándar compatible con Gunicorn / uWSGI / Render."""
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    headers = [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]

    if method == "OPTIONS":
        start_response("204 No Content", headers)
        return [b""]

    if path in ("/", "/health"):
        data = json.dumps({"status": "ok", "service": "content-moderation-api"}).encode("utf-8")
        headers.extend([("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(data)))])
        start_response("200 OK", headers)
        return [data]

    if path == "/api/dashboard":
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        pos = int(qs["pos"][0]) if "pos" in qs else None
        data = json.dumps(dash_instance.payload(pos), ensure_ascii=False).encode("utf-8")
        headers.extend([("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(data)))])
        start_response("200 OK", headers)
        return [data]

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

    dash = dash_instance
    if args.refresh:
        dash = Dashboard(refresh=True, rate_eps=args.rate)

    port = args.serve or (int(os.environ["PORT"]) if "PORT" in os.environ else None)
    if port:
        print(f"API lista: http://0.0.0.0:{port}/api/dashboard", flush=True)
        ThreadingHTTPServer(("0.0.0.0", port), make_handler(dash)).serve_forever()
    else:
        print(json.dumps(dash.payload(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
