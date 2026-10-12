# INFORME CONSOLIDADO DE LABORATORIO (WORKSHOPS 1, 2 Y 3)
## Plataforma de Streaming de Video: Moderación de Contenido mediante Algoritmos Probabilísticos
**Curso:** Lógica III – Semestre 2026-2  
**Equipo:** 4  
**Autores:** Arley, Juan Camilo, Andrés Buitrago  

---

### 1. Resumen Ejecutivo y Contexto Big Data (Workshop 1)

El crecimiento exponencial de las plataformas de video en tiempo real imposibilita el procesamiento determinista exhaustivo de cada elemento subido. El objetivo de este proyecto consistió en diseñar, medir e integrar una arquitectura completa de ingestión, particionamiento, filtrado y modelado estructural de contenido aplicando algoritmos aleatorizados y probabilísticos.

#### Task 1: Estimación a $10\times$ Crecimiento
A partir de la muestra de ingestión observada ($10\,000$ videos en un periodo de $0.52$ días, tasa base de $\approx 0.22\text{ videos/s}$):
- **Tasa Proyectada ($10\times$):** $\approx 2.22\text{ uploads/s}$ a nivel de plataforma.
- **Volumen de Metadatos:** Con un payload promedio de $160\text{ Bytes}$ por registro (excluyendo el archivo binario del video), la plataforma genera $\approx 30.7\text{ MB/día}$ y $\approx 11.2\text{ GB/año}$.
- **Conclusión de Arquitectura:** El almacenamiento de metadatos es perfectamente manejable en memoria o bases de datos no relacionales, pero el cuello de botella radica en la latencia de asignación de revisores y en la detección de cuentas fraudulentas sin retrasar la publicación de videos legítimos.

---

### 2. Algoritmos Aleatorizados, Hashing y Cotas de Concentración (Workshop 1)

#### Task 2: QuickSort Aleatorizado vs. Determinista
Se evaluó el tiempo de ordenamiento de la cola de moderación por duración (`duration_sec`):
- **Entrada Ya Ordenada / Inversa:** El algoritmo determinista (con pivote fijo final) degenera en comportamiento $\mathcal{O}(n^2)$, requiriendo hasta $4\,352.9\text{ ms}$ para $n=10\,000$.
- **QuickSort Aleatorizado:** Al seleccionar el pivote de manera pseudoaleatoria uniforme, el tiempo promedio para $n=10\,000$ se reduce a solo $14.5\text{ ms}$ (**speedup de más de $300\times$**), manteniendo de forma empírica la cota esperada $\mathcal{O}(n \log n)$ sin importar el orden previo del lote.

#### Tasks 3 y 4: Universal Sharding y Power of Two Choices
- **Sharding entre 32 Revisores:** La función de hash universal distribuye los $10\,000$ videos entre 32 trabajadores con una media de $312.5$ videos por trabajador ($\sigma = 16.8$, ratio de desbalance máx/media de solo $1.15$), minimizando cuellos de botella de asignación.
- **Bucketing de Videos Pendientes (Two Choices vs. Chaining):**
  - Con Chaining estándar ($h_1$), la carga máxima observada en $m=128$ buckets fue de $102$ elementos ($\sigma = 9.67$).
  - Con **Power of Two Choices** ($d=2$), al comparar dos buckets independientes y colocar el elemento en el menos cargado, la carga máxima descendió a $80$ elementos y la desviación estándar cayó a **$0.97$**. La masa de probabilidad se concentra fuertemente en torno a la media $\mu$, eliminando colas largas.

#### Task 5: Análisis de Concentración con Cotas de Chernoff
Se modeló la probabilidad de que la tasa de videos marcados de un usuario supere un umbral sospechoso (definido como $2\times$ la tasa global del $10.17\%$). Aplicando la cota de entropía relativa:
$$P[X \ge k] \le \exp\left(-n \cdot D_{\text{KL}}\left(\frac{k}{n} \,\Big\|\, p_0\right)\right)$$
De los $1\,121$ uploaders evaluados con $\ge 5$ subidas, $140$ superaron la tasa del $20.3\%$. Sin embargo, ninguno arrojó una cota de Chernoff menor al nivel de significancia $\alpha=0.01$. **Conclusión:** Las tasas elevadas en cuentas con pocas subidas (5 a 10 videos) son consistentes con ruido binomial aleatorio; la cota protege a la plataforma de penalizar o bloquear falsos sospechosos por pura fluctuación muestral.

---

### 3. Modelado de Streaming, Filtros Compactos y Momentos de Frecuencia (Workshop 2)

#### Tasks 1 y 2: Filtro de Bloom para Reincidentes
Se implementó un filtro de Bloom con doble hashing de Kirsch-Mitzenmacher ($h_i(x) = h_1(x) + i \cdot h_2(x) \pmod m$) sobre $801$ usuarios marcados:
- Con $b=8\text{ bits/usuario}$ ($k=6$ funciones hash), la tasa empírica de falsos positivos fue de **$2.10\%$**, coincidiendo de forma casi idéntica con la cota teórica de **$2.15\%$**.
- Con $b=16\text{ bits/usuario}$, la tasa empírica fue de **$0.00\%$** (teórica de $0.045\%$), con cero falsos negativos garantizados por definición matemática.

#### Tasks 3 y 4: Reservoir Sampling e HyperLogLog
- **Reservoir Sampling (Algoritmo R):** Estimar el promedio de vistas en la primera hora (`view_count_1h`) por categoría sobre un flujo continuo de longitud desconocida arrojó un error porcentual medio del $11.8\%$ con $k=100$, que se redujo al **$5.9\%$ con $k=500$**.
- **HyperLogLog ($m \in \{16, 32, 64, 128\}$):** El conteo de usuarios únicos por día mediante HLL consumió únicamente entre $96$ y $768\text{ bits}$ de memoria, logrando un ahorro de espacio superior al **$99.8\%$** frente a almacenar el conjunto explícito de identificadores, con errores relativos empíricos ($7.2\%$ en $m=128$) alineados con la cota teórica de $1.04/\sqrt{m} \approx 9.1\%$.

#### Task 5: Momentos de Frecuencia ($F_k$) y Detección de Olas de Spam
Calculando los momentos exactos sobre categorías en una ventana móvil de $1\,000$ videos:
- $F_0 = 10$, $F_1 = 1\,000$, $F_2 \approx 100\,500$.
- La probabilidad de colisión $F_2 / F_1^2 \approx 0.1005$ es casi idéntica a la distribución uniforme ($1/F_0 = 0.1000$).
- **Mecanismo de Alerta:** Monitorear $z\text{-score}(F_2) > 2.0$ y la tasa de marcado móvil detectó anomalías temporales causadas por olas repentinas de spam en categorías específicas (como *Ciencia* o *Videojuegos*), disparando el protocolo de alerta en el panel de control.

---

### 4. Cadenas de Markov, PageRank y 2-SAT Aleatorizado (Workshop 3)

#### Tasks 1, 2 y 4: Cadena Discreta de Markov y Caminata Lazy
- **Clasificación:** La matriz de transiciones $M$ entre las 10 categorías constituye una cadena **irreducible, ergódica y aperiódica** (periodo $1$), sin estados absorbentes (*sinks*).
- **Distribución Estacionaria $\pi$:** Convergió en solo 9 iteraciones con un residuo $< 10^{-15}$. La categoría de mayor atracción a largo plazo (*gravity well*) es **Videojuegos** ($\pi = 10.56\%$), a pesar de que el ranking bruto por volumen de subidas está liderado por **Deportes** ($10.49\%$).
- **Lazy Random Walk ($L = (I+P)/2$):** Una caminata de $50\,000$ pasos arrojó una variación total de solo **$0.58\%$** respecto a la distribución teórica $\pi$, confirmando la rapidez de mezcla.

#### Task 3: PageRank con Overlay de Contenido Marcado
Aplicando iteración de potencia con amortiguamiento $d=0.85$, los valores de PageRank resultaron muy cercanos entre sí (rango bruto de apenas $0.74\text{ pp}$), reflejando una red de navegación casi balanceada. La correlación de Spearman entre PageRank y frecuencia bruta fue de **$\rho = 0.62$**. El reescalado visual $0\text{--}100$ en el gráfico de Radar permitió apreciar las categorías con mayor desajuste entre subidas y retención estructural, superponiendo la fracción marcada (`flagged_frac`).

#### Task 5: Resolución de Políticas con Papadimitriou (2-SAT)
Para las 4 categorías con mayor índice de riesgo ($\pi_c \cdot \text{flagged\_frac}_c$: *Entretenimiento, Salud, Deportes y Cocina*), se definieron 5 cláusulas de políticas de moderación ($R_c \lor T_c$, con restricción de capacidad presupuestal $\neg R_a \lor \neg R_b$). El algoritmo aleatorizado de Papadimitriou halló una asignación satisfactible en el primer intento y con solo 1 cambio de variable (*flip*), garantizando el cumplimiento de todas las restricciones operativas.

---

### 5. Conclusiones y Dashboard Integrado
1. **Sinergia Algorítmica:** La combinación de filtros compactos en streaming (Bloom, HLL) con colas de dos elecciones y QuickSort aleatorizado permite absorber picos de tráfico en tiempo real con uso mínimo de recursos computacionales.
2. **Dashboard de 4 Paneles:** Construido en Next.js con Tailwind y Recharts, el panel interactivo consume la API REST unificada en tiempo real (`GET /api/dashboard`), permitiendo a los operadores alternar vistas de sharding, explorar la simulación del stream y verificar el cumplimiento de políticas 2-SAT.
