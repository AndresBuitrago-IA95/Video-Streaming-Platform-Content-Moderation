"""Generate reproducible synthetic datasets for Workshops 1, 2, and 3."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
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
FLAG_REASONS = ("Contenido inapropiado", "Desinformacion", "Spam", "Violencia")
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


def generate_datasets(count: int, uploader_count: int, seed: int) -> tuple[list, list, list]:
    """Return W1 videos, sequenced W2 stream, and W3 category-transition edges."""
    if count < 2:
        raise ValueError("count debe ser al menos 2 para construir transiciones")
    if uploader_count < 1:
        raise ValueError("uploader_count debe ser positivo")

    rng = random.Random(seed)
    start = datetime(2026, 10, 1)
    stream = []
    for sequence in range(1, count + 1):
        category = rng.choice(CATEGORIES)
        flagged = rng.random() < FLAG_PROBABILITY[category]
        timestamp = start + timedelta(seconds=rng.randrange(24 * 60 * 60))
        video_id = f"VID_{sequence:06d}"
        stream.append({
            "video_id": video_id,
            "upload_time": timestamp.isoformat(timespec="seconds"),
            "uploader_id": f"USER_{rng.randrange(uploader_count):06d}",
            "category": category,
            "duration_sec": rng.randint(1, 600),
            "flag_reason": rng.choice(FLAG_REASONS) if flagged else "",
            "is_flagged": flagged,
            "view_count_1h": min(100_000, int(rng.lognormvariate(6.0, 1.0))),
        })

    stream.sort(key=lambda row: (row["upload_time"], row["video_id"]))
    for sequence, row in enumerate(stream, start=1):
        row["stream_seq"] = sequence

    videos_w2 = [dict(row) for row in stream]
    videos_w1 = [
        {key: value for key, value in row.items() if key not in ("stream_seq", "view_count_1h")}
        for row in videos_w2
    ]
    rng.shuffle(videos_w1)

    by_uploader = defaultdict(list)
    for row in stream:
        by_uploader[row["uploader_id"]].append(row)

    edges = defaultdict(lambda: {"count": 0, "flagged": 0, "views": 0})
    for uploads in by_uploader.values():
        for source, target in zip(uploads, uploads[1:]):
            edge = edges[(source["category"], target["category"])]
            edge["count"] += 1
            edge["flagged"] += int(source["is_flagged"])
            edge["views"] += source["view_count_1h"]

    transitions = []
    for index, ((source, target), stats) in enumerate(sorted(edges.items()), start=1):
        transitions.append({
            "edge_id": f"e{index:03d}",
            "from_category": source,
            "to_category": target,
            "transition_count": stats["count"],
            "flagged_frac": stats["flagged"] / stats["count"],
            "avg_view_count_1h": stats["views"] / stats["count"],
        })

    return videos_w1, videos_w2, transitions


def write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000, help="cantidad de videos (default: 10000)")
    parser.add_argument("--uploaders", type=int, default=2_000, help="cantidad posible de uploaders (default: 2000)")
    parser.add_argument("--seed", type=int, default=42, help="semilla para reproducibilidad")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR, help="directorio donde guardar los JSON")
    args = parser.parse_args()

    if args.count < 2 or args.uploaders < 1:
        parser.error("--count debe ser >= 2 y --uploaders debe ser >= 1")

    w1, w2, w3 = generate_datasets(args.count, args.uploaders, args.seed)
    write_json(args.output_dir / "videos_equipo4.json", w1)
    write_json(args.output_dir / "videos_workshop2_equipo4.json", w2)
    write_json(args.output_dir / "transiciones_workshop3_equipo4.json", w3)
    print(
        f"Generados {len(w1)} videos W1, {len(w2)} eventos W2 y "
        f"{len(w3)} transiciones W3 en {args.output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
