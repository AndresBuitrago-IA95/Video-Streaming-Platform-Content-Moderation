"use client";

import { useState } from "react";
import BucketDistributionChart from "@/components/BucketDistributionChart";
import CategoryFlowPanel from "@/components/CategoryFlowPanel";
import LiveMetricsPanel from "@/components/LiveMetricsPanel";
import LshThresholdOutcomePanel from "@/components/LshThresholdOutcomePanel";
import MapReducePanel from "@/components/MapReducePanel";
import PageRankPanel from "@/components/PageRankPanel";
import RuntimeChart from "@/components/RuntimeChart";
import SimilarityNeighborsPanel from "@/components/SimilarityNeighborsPanel";
import { Segmented, Stat } from "@/components/ui";
import { API_URL, useDashboard } from "@/lib/useDashboard";

export default function DashboardPage() {
  const { data, error, lastUpdated, ticks } = useDashboard(5000);
  const [showCapacity, setShowCapacity] = useState(false);
  const [unitFilter, setUnitFilter] = useState<"all" | "w13" | "w4" | "w5">("all");

  return (
    <main className="mx-auto w-full max-w-[1550px] flex-1 px-4 py-6 sm:px-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-violet-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">
              Lógica III · Grupo 4
            </span>
            <span className="text-xs text-slate-500">Integración Completa Workshops 1, 2, 3, 4 y 5</span>
          </div>
          <h1 className="mt-1 bg-gradient-to-r from-violet-300 via-sky-300 to-cyan-200 bg-clip-text text-3xl font-bold text-transparent sm:text-4xl">
            Video Streaming Platform · Content Moderation
          </h1>
          <p className="mt-1 max-w-3xl text-xs sm:text-sm text-slate-400">
            Plataforma unificada de moderación: Hashing, QuickSort, Streaming (Bloom, HLL, Reservoir, Fk),
            Markov/PageRank/2-SAT (W1–W3), MapReduce paralelo con mitigación de skew (W4) y búsqueda de
            cuentas coordinadas con k-Shingles, MinHash/LSH e Hiperplanos Aleatorios (W5).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            value={unitFilter}
            onChange={setUnitFilter}
            options={[
              { value: "all", label: "Todos (A–H)" },
              { value: "w13", label: "W1–W3 (A–D)" },
              { value: "w4", label: "W4 MapReduce (E–F)" },
              { value: "w5", label: "W5 Similitud & LSH (G–H)" },
            ]}
          />

          <button
            onClick={() => setShowCapacity(!showCapacity)}
            className="rounded-lg border border-violet-400/30 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200 transition hover:bg-violet-500/20"
          >
            {showCapacity ? "Ocultar Big Data Context" : "Big Data Context (W1 T1)"}
          </button>

          <div
            id="connection-status"
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${
              error
                ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
                : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${error ? "bg-rose-400" : "animate-pulse bg-emerald-400"}`} />
            {error
              ? `Sin conexión (${error})`
              : lastUpdated
                ? `En vivo ${lastUpdated.toLocaleTimeString()}`
                : "Conectando…"}
          </div>
        </div>
      </header>

      {/* Banner de Big Data Context (W1 Task 1) */}
      {showCapacity && data && (
        <section className="mb-6 rounded-2xl border border-violet-400/30 bg-slate-900/80 p-5 shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-top-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-violet-200">
              W1 Task 1: Estimación de Tráfico y Almacenamiento a 10x Crecimiento de Usuarios
            </h3>
            <span className="text-[11px] text-slate-400">{data.capacity.assumption}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Stat
              label="Tasa Actual de Subidas"
              value={`${data.capacity.uploads_per_sec.toFixed(2)} /s`}
              hint={`Dataset: ${data.capacity.records.toLocaleString()} vids en ${data.capacity.span_days.toFixed(1)} días`}
            />
            <Stat
              label="Tasa Proyectada (10x)"
              value={`${data.capacity.uploads_per_sec_growth.toFixed(1)} /s`}
              hint="Crecimiento de usuarios ×10"
              tone="good"
            />
            <Stat
              label="Tamaño Medio Metadatos"
              value={`${data.capacity.avg_metadata_bytes.toFixed(0)} Bytes`}
              hint="JSON solo metadatos (sin video)"
            />
            <Stat
              label="Almacenamiento / Día"
              value={`${(data.capacity.storage_per_day_bytes / (1024 * 1024)).toFixed(1)} MB/día`}
              hint="Capacidad para ingestión continua"
            />
            <Stat
              label="Almacenamiento / Año"
              value={`${(data.capacity.storage_per_year_bytes / (1024 * 1024 * 1024)).toFixed(2)} GB/año`}
              hint="Retención a 1 año en BD no relacional"
              tone="good"
            />
          </div>
        </section>
      )}

      {error && (
        <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          No se pudo contactar <code className="font-mono">{API_URL}</code>. Inicia la API con{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">
            py backend/aggregate_api.py --serve 8000
          </code>
          {data && " — mostrando los datos cacheados en memoria."}
        </div>
      )}

      {!data ? (
        <div className="grid gap-5 lg:grid-cols-2">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-96 animate-pulse rounded-2xl border border-white/10 bg-slate-900/50" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {(unitFilter === "all" || unitFilter === "w13") && (
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />
                Workshops 1–3 · Algoritmos Probabilísticos, Streaming y Cadenas de Markov (Paneles A–D)
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <BucketDistributionChart data={data.panel_a_bucket_load} />
                <RuntimeChart data={data.panel_b_runtimes} />
                <LiveMetricsPanel data={data.panel_c_realtime} ticks={ticks} />
                <PageRankPanel data={data.panel_d_pagerank} />
              </div>
            </section>
          )}

          {(unitFilter === "all" || unitFilter === "w4") && data.panel_e_mapreduce && data.panel_f_category_flow && (
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                Workshop 4 · MapReduce Paralelo, PageRank S10, Costos y Mitigación de Skew S14 (Paneles E–F)
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <MapReducePanel data={data.panel_e_mapreduce} />
                <CategoryFlowPanel data={data.panel_f_category_flow} />
              </div>
            </section>
          )}

          {(unitFilter === "all" || unitFilter === "w5") && data.panel_g_neighbors && data.panel_h_threshold_outcome && (
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Workshop 5 · Detección de Cuentas Coordinadas: k-Shingles, MinHash/LSH e Hiperplanos (Paneles G–H)
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                <SimilarityNeighborsPanel data={data.panel_g_neighbors} />
                <LshThresholdOutcomePanel data={data.panel_h_threshold_outcome} />
              </div>
            </section>
          )}
        </div>
      )}

      <footer className="mt-8 flex flex-wrap items-center justify-between border-t border-white/10 pt-4 text-[11px] text-slate-500">
        <span>Universidad de Antioquia · Lógica III (2026-2) · Equipo 4</span>
        <span>Pipeline unificado: Hashing, QuickSort, Bloom, HLL, Reservoir, Chernoff, Markov/2-SAT, MapReduce (W4) & MinHash/LSH (W5)</span>
      </footer>
    </main>
  );
}
