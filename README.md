# Video Streaming Platform – Content Moderation (Lógica III · Equipo 4)

Dashboard de 4 paneles que integra los workshops 1–3: hashing (Chaining vs. Two Choices),
QuickSort aleatorizado vs. determinista, Bloom filter, momentos de frecuencia (F0/F1/F2),
cotas de Chernoff y PageRank sobre la matriz de transición de categorías.

## Estructura

- `Dashboard_Integrado/analytics/` – motor analítico (`metrics_and_graphs.py`) y API (`aggregate_api.py`).
- `Dashboard_Integrado/frontend/` – Next.js + TypeScript + Tailwind + Recharts.
- Carpetas `Equipo_4_logica_3*` y `Workshop*_Juan_Camilo` – solo los datos/resultados que consume el dashboard.

## Ejecución

```bash
pip install -r requirements.txt
py Dashboard_Integrado/analytics/aggregate_api.py --serve 8000   # API en http://localhost:8000/api/dashboard

cd Dashboard_Integrado/frontend
npm install
npm run dev                                                     # http://localhost:3000
```

Opcional: `NEXT_PUBLIC_API_URL` para apuntar a otra URL de la API.
