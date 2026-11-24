# Video Streaming Platform – Content Moderation
> **Lógica III (2026-2) · Equipo 4**  
> Integración de Algoritmos Probabilísticos, Streaming, Análisis de Grafos, MapReduce Paralelo y Búsqueda de Similitud / LSH (Workshops 1, 2, 3, 4 y 5).

---

## 1. Arquitectura del Proyecto

El repositorio cuenta con una **estructura unificada** y autosuficiente:

```text
├── backend/
│   ├── data/                           # Datasets originales y generados (W1, W2, W3, W4, W5)
│   │   ├── videos_equipo4.json
│   │   ├── videos_workshop2_equipo4.json
│   │   ├── transiciones_workshop3_equipo4.json
│   │   ├── fragments_w4/               # >=8 archivos fragmento JSONL para Map paralelo (W4)
│   │   ├── transiciones_mapreduce_workshop4_equipo4.json
│   │   ├── node_summary_workshop4_equipo4.json
│   │   └── uploaders_workshop5_equipo4.json
│   ├── algorithms/                     # Módulos algorítmicos
│   │   ├── hashing.py                  # Universal sharding & Power of Two Choices (W1)
│   │   ├── quicksort.py                # QuickSort determinista vs aleatorizado (W1)
│   │   ├── bloom.py                    # Bloom filter con doble hashing Kirsch-Mitzenmacher (W2)
│   │   ├── hyperloglog.py              # HyperLogLog con corrección de rango (W2)
│   │   ├── reservoir.py                # Reservoir Sampling (Algoritmo R) (W2)
│   │   ├── markov.py                   # DTMC, Lazy Walk & Papadimitriou 2-SAT (W3)
│   │   ├── mapreduce.py                # Runner MapReduce paralelo, S10 PageRank, costos, R-sweep y S14 skew (W4)
│   │   └── similarity.py               # k-Shingles (S21), MinHash/LSH (S25), Hiperplanos, LCS & Outcome Test (W5)
│   ├── config.py                       # Configuración de rutas
│   ├── metrics_and_graphs.py           # Chernoff bounds, momentos Fk y PageRank
│   ├── streaming.py                    # Motor de simulación de streaming continuo
│   ├── static_results.py               # Generador y caché de benchmarks estáticos (W1–W5)
│   ├── generate_data.py                # Generador reproducible de datasets W1, W2 y W3
│   └── aggregate_api.py                # Servidor HTTP / API REST unificada (puerto 8000)
├── frontend/                           # Aplicación Next.js 16 + React 19 + TypeScript + Tailwind v4
│   ├── src/
│   │   ├── app/                        # App Router (page.tsx, layout.tsx, globals.css)
│   │   ├── components/                 # Paneles Recharts (A–D, E–F de W4, G–H de W5 y UI compartido)
│   │   └── lib/                        # Tipos e hook useDashboard (polling en vivo)
│   └── package.json
├── INFORME_INTEGRADO_WORKSHOPS_1_2_3.md # Informe técnico consolidado W1–W3
├── GUIA_WORKSHOPS_4_5_Y_DASHBOARD.md    # Explicación detallada de W4, W5 y funcionamiento completo del dashboard
├── GUION_PRESENTACION_WORKSHOPS.md      # Guion de presentación
├── screenshots/                         # Evidencia visual del dashboard
├── requirements.txt                    # Dependencias Python (pandas, numpy, gunicorn)
└── README.md
```

---

## 2. Cobertura de Tareas según el Excel (`Workshop_1-2-3.xlsx`)

| Workshop | Tarea | Descripción / Implementación | Ubicación en el Código |
|---|---|---|---|
| **W1** | **Task 1: Big Data Context** | Estimación de subidas/segundo y volumen anual de metadatos ante crecimiento $10\times$. | `backend/static_results.py` & Header Dashboard |
| **W1** | **Task 2: Randomized Algorithm** | QuickSort determinista vs. aleatorizado por `duration_sec`, validado contra ordenamiento exacto. | `backend/algorithms/quicksort.py` & **Panel B** |
| **W1** | **Task 3: Universal Hashing** | Sharding de `uploader_id` entre 32 revisores humanos; balanceo de carga y conteo de colisiones. | `backend/algorithms/hashing.py` & **Panel A** |
| **W1** | **Task 4: Hash Table Operations** | Tabla hash por categoría de videos pendientes de revisión: Chaining vs. Power of Two Choices ($d=2$). | `backend/algorithms/hashing.py` & **Panel A** |
| **W1** | **Task 5: Probability Analysis** | Cotas de Chernoff sobre la tasa de videos marcados por uploader para detección de cuentas sospechosas ($\alpha=0.01$). | `backend/metrics_and_graphs.py` & **Panel C** |
| **W2** | **Task 1: Stream Model** | Standing Query: Tasa de marcados por categoría en ventana móvil de 1 000 videos. Ad-hoc Query: Distinct uploaders hoy. | `backend/streaming.py` & **Panel C** |
| **W2** | **Task 2: Bloom Filter** | Filtro de Bloom para uploaders reincidentes; tasa de falsos positivos teórica vs. empírica para $b \in \{4, 8, 12, 16\}$. | `backend/algorithms/bloom.py` & **Panel C** |
| **W2** | **Task 3: Stream Sampling** | Reservoir Sampling (Algoritmo R): Estimación de `view_count_1h` medio por categoría en $k \in \{100, 300, 500\}$. | `backend/algorithms/reservoir.py` & **Panel C** |
| **W2** | **Task 4: Distinct Count** | HyperLogLog para uploaders distintos por día ($m \in \{16, 32, 64, 128\}$), contrastando error vs. memoria. | `backend/algorithms/hyperloglog.py` & **Panel C** |
| **W2** | **Task 5: Frequency Moments** | Momentos exactos $F_0, F_1, F_2$ por categoría; alerta automática de *Spam Waves* mediante $z\text{-score}(F_2) > 2$. | `backend/streaming.py` & **Panel C** |
| **W3** | **Task 1: DTMC & States** | Construcción de la matriz estocástica $M$; verificación de estados absorbentes (ninguno) e irreducibilidad. | `backend/algorithms/markov.py` & **Panel D** |
| **W3** | **Task 2: Stationary Distribution** | Cálculo iterativo de $\pi$; identificación del pozo de atracción (*gravity well*) de la plataforma. | `backend/algorithms/markov.py` & **Panel D** |
| **W3** | **Task 3: PageRank** | PageRank ($d=0.85$) sobre la red de categorías vs. ranking por frecuencia bruta de subidas. | `backend/metrics_and_graphs.py` & **Panel D** |
| **W3** | **Task 4: Lazy Random Walk** | Caminata aleatoria floja con auto-bucle de $1/2$ ($50\,000$ pasos); validación de convergencia empírica hacia $\pi$. | `backend/algorithms/markov.py` & **Panel D** |
| **W3** | **Task 5: Randomized 2-SAT** | Algoritmo de Papadimitriou para resolver 5 políticas de moderación sobre variables booleanas de categorías en riesgo. | `backend/algorithms/markov.py` & **Panel D** |
| **W3** | **Task 6: Dashboard** | Panel A (Hashing/Sharding), Panel B (Runtimes), Panel C (Stream & Fk), Panel D (PageRank con `flagged_frac` overlay). | `frontend/src/` |
| **W4** | **Task 1: MapReduce Pipeline** | Job 1 (transiciones por uploader desde ≥8 fragmentos con ≥2 workers) y Job 2 (Node Summary: `out`, `in`, `net_flow`, `flagged_frac`, `avg_view_count_1h`), validado contra Unidad 3. | `backend/algorithms/mapreduce.py` & **Panel F** |
| **W4** | **Task 2: S10 PageRank MR** | Multiplicación iterativa matriz-vector en MapReduce (`Map: (j, p(i,j)*v_i)`, `Reduce: sum`) comparada contra Unidad 3 dentro de `1e-4`. | `backend/algorithms/mapreduce.py` & **Panel F** |
| **W4** | **Task 3: Cost Analysis** | Shuffle con/sin combiner a 1x (100k), 2x (200k) y 4x (400k), chequeo lineal ($R^2$), extrapolación a 10x (1M) y costo S10 (pares/iter × iteraciones). | `backend/algorithms/mapreduce.py` & **Panel E** |
| **W4** | **Task 4: Reducer Size & Replication** | Hot key (`uploader_id` más activo), reporte de $(r, q)$ por job y barrido de Job 1 con $R \in \{1, 2, 4, 8\}$ reducers. | `backend/algorithms/mapreduce.py` & **Panel E** |
| **W4** | **Task 5: S14 Skew & Mitigation** | Ola de spam (≥40% en una categoría), speedup/eficiencia/LBF para $P \in \{1, 2, 4, 8\}$ y mitigación con Salting + Combiner. | `backend/algorithms/mapreduce.py` & **Panel E** |
| **W4** | **Task 6: Dashboard (E–F)** | **Panel E** (Speedup/Eficiencia vs workers y Shuffle con/sin combiner) y **Panel F** (Categorías por `flagged_frac` y `net_flow`). | `frontend/src/components/MapReducePanel.tsx`, `CategoryFlowPanel.tsx` |
| **W5** | **Task 1: Representations & Distances** | Conjuntos ($k=3$ shingles) y vectores (shares + 2 métricas z-scored sin `flagged_frac`) para 1 000 uploaders; distribuciones en 5 000 pares; correlación Jaccard/Cosine/LCS en 500 pares; concentración de distancias. | `backend/algorithms/similarity.py` & **Panel G** |
| **W5** | **Task 2: Random Hyperplanes** | Firmas de hiperplanos aleatorios ($n \in \{16, 32, 64, 128\}$), verificación Charikar ($1-\theta/180$) en 1 000 pares, Cosine LSH banding y `recall@5` en 50 queries. | `backend/algorithms/similarity.py` & **Panel G** |
| **W5** | **Task 3: S21 k-Shingles** | Comparación $k \in \{2, 3, 4\}$: tamaño medio, posibles vs observados, separación Jaccard intra-cluster vs inter-cluster y selección del mejor $k$. | `backend/algorithms/similarity.py` & **Panel G** |
| **W5** | **Task 4: S25 Threshold Design** | MinHash $n=100$ sobre el runner MapReduce de Unidad 4 con bandas en Reduce; diseño $(b=20, r=5)$ para $s \ge 0.6$ y $\text{FNR}(0.8) \le 1\%$; precisión/recall vs fuerza bruta (~500 000 pares). | `backend/algorithms/similarity.py` & **Panel H** |
| **W5** | **Task 5: Top-5 Neighbors & Outcome Test** | Top-5 vecinos en ≥20 consultas por MinHash/LSH, Cosine LSH y LCS (solo candidatos); `overlap@5` y prueba de resultado sobre `flagged_frac` vs 5 uploaders aleatorios. | `backend/algorithms/similarity.py` & **Paneles G–H** |
| **W5** | **Task 6: Dashboard (G–H)** | **Panel G** (selector de uploader con Top-5 vecinos por método, candidatos y `flagged_frac`) y **Panel H** (diseño de umbral S25 P/R y Outcome Test). | `frontend/src/components/SimilarityNeighborsPanel.tsx`, `LshThresholdOutcomePanel.tsx` |

---

## 3. Instrucciones de Instalación y Ejecución

### Prerrequisitos
* Python 3.10+ (en Windows se utiliza `py`)
* Node.js 18+ y npm

### Paso 1: Configurar el Backend
```bash
# 1. Instalar dependencias Python
pip install -r requirements.txt

# 2. (Opcional) Regenerar los tres datasets con semilla reproducible
# Por seguridad, usa otra carpeta si no quieres sobrescribir los datos actuales.
py backend/generate_data.py --seed 42 --output-dir backend/data/generated

# 3. Iniciar el servidor API (puerto 8000)
py backend/aggregate_api.py --serve 8000
```
> *Nota:* Para reemplazar los datasets activos, genera en `backend/data` (haz una copia de seguridad primero) y recalcula `backend/static_results.json` con `py backend/aggregate_api.py --refresh` antes de iniciar el backend. El backend carga y cachea los resultados estáticos al arrancar.

### Paso 2: Iniciar el Frontend
En una segunda terminal:
```bash
# 1. Entrar al directorio frontend
cd frontend

# 2. Instalar paquetes de Node
npm install

# 3. Iniciar el servidor Next.js
npm run dev
```

Abra su navegador en: **`http://localhost:3000`**

### Despliegue

**Render (backend):**
* Root Directory: raíz del repositorio.
* Build Command: `pip install -r requirements.txt`
* Start Command: `gunicorn backend.aggregate_api:app --bind 0.0.0.0:$PORT`
* Health Check Path: `/health`

**Vercel (frontend):**
* Importa el mismo repositorio y establece **Root Directory** en `frontend`.
* Define `NEXT_PUBLIC_API_URL` como `https://<tu-servicio>.onrender.com/api/dashboard`.
* Si cambias esta variable, vuelve a desplegar para que Next.js la incluya en el build.

El panel de W2 permite alternar entre stream/Fk, HyperLogLog y reservoir sampling. La vista HLL compara gráficamente la estimación con el conteo exacto y el error frente a memoria. La medición del filtro de Bloom se calcula con los eventos consumidos hasta la posición actual del stream.

---

## 4. Endpoints de la API

* **`GET /api/dashboard`**: Devuelve la carga consolidada con el estado actual del streaming (avanza en tiempo real a una tasa simulada de 25 eventos/segundo).
* **`GET /api/dashboard?pos=N`**: Permite fijar el cursor de lectura del stream en un evento específico para propósitos de auditoría o pruebas.

El [guion de exposición](GUION_PRESENTACION_WORKSHOPS.md) distribuye el contenido y la demostración entre Arley, Juan Camilo y Andrés, con cinco minutos de margen para preguntas.
