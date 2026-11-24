"""Rutas del proyecto. Todo el código y los datos viven dentro de este repositorio."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

VIDEOS_W1 = DATA / "videos_equipo4.json"               # Unidad 1: 10 000 videos
VIDEOS_W2 = DATA / "videos_workshop2_equipo4.json"     # Unidad 2: + stream_seq, view_count_1h
TRANSITIONS_W3 = DATA / "transiciones_workshop3_equipo4.json"  # Unidad 3: aristas entre categorías
FRAGMENTS_W4_DIR = DATA / "fragments_w4"               # Unidad 4: >= 8 fragmentos JSONL para Map paralelo
EDGES_W4 = DATA / "transiciones_mapreduce_workshop4_equipo4.json"  # Unidad 4: aristas construidas con MapReduce
NODE_SUMMARY_W4 = DATA / "node_summary_workshop4_equipo4.json"     # Unidad 4: resumen de nodos por categoría
UPLOADERS_W5 = DATA / "uploaders_workshop5_equipo4.json"           # Unidad 5: secuencias, shingles, MinHash y vecinos
STATIC_CACHE = ROOT / "static_results.json"            # resultados costosos precalculados
