# Video Streaming Platform – Content Moderation
> **Lógica III (2026-2) · Equipo 4**  
> Integración de Algoritmos Probabilísticos, Streaming y Análisis de Grafos (Workshops 1, 2 y 3).

---

## 1. Arquitectura del Proyecto

El repositorio cuenta con una **estructura unificada** y autosuficiente:

```text
├── backend/
│   ├── data/                           # Datasets originales (W1, W2 y transiciones W3)
│   │   ├── videos_equipo4.json
│   │   ├── videos_workshop2_equipo4.json
│   │   └── transiciones_workshop3_equipo4.json
│   ├── algorithms/                     # Módulos de algoritmos probabilísticos
│   │   ├── hashing.py                  # Universal sharding & Power of Two Choices
│   │   ├── quicksort.py                # QuickSort determinista vs aleatorizado
│   │   ├── bloom.py                    # Bloom filter con doble hashing Kirsch-Mitzenmacher
│   │   ├── hyperloglog.py              # HyperLogLog con corrección de rango
│   │   ├── reservoir.py                # Reservoir Sampling (Algoritmo R)
│   │   └── markov.py                   # DTMC, Lazy Walk & Papadimitriou 2-SAT
│   ├── config.py                       # Configuración de rutas
│   ├── metrics_and_graphs.py           # Chernoff bounds, momentos Fk y PageRank
│   ├── streaming.py                    # Motor de simulación de streaming continuo
│   ├── static_results.py               # Generador y caché de benchmarks estáticos
│   ├── generate_data.py                # Generador reproducible de datasets W1, W2 y W3
│   └── aggregate_api.py                # Servidor HTTP / API REST unificada (puerto 8000)
├── frontend/                           # Aplicación Next.js 16 + React 19 + TypeScript + Tailwind v4
│   ├── src/
│   │   ├── app/                        # App Router (page.tsx, layout.tsx, globals.css)
│   │   ├── components/                 # Paneles Recharts (A, B, C, D y UI compartido)
│   │   └── lib/                        # Tipos e hook useDashboard (polling en vivo)
│   └── package.json
├── INFORME_INTEGRADO_WORKSHOPS_1_2_3.md # Informe técnico consolidado (requisito de entrega)
├── screenshots/                         # Evidencia visual del dashboard para el informe
├── requirements.txt                    # Dependencias Python (pandas, numpy)
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
