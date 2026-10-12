"use client";

import BucketDistributionChart from "@/components/BucketDistributionChart";
import LiveMetricsPanel from "@/components/LiveMetricsPanel";
import PageRankPanel from "@/components/PageRankPanel";
import RuntimeChart from "@/components/RuntimeChart";
import { API_URL, useDashboard } from "@/lib/useDashboard";

export default function DashboardPage() {
  const { data, error, lastUpdated, ticks } = useDashboard(5000);

  return (
    <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 sm:px-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-300">
            Lógica III · Equipo 4
          </p>
          <h1 className="bg-gradient-to-r from-violet-300 via-sky-300 to-cyan-200 bg-clip-text text-3xl font-bold text-transparent sm:text-4xl">
            Dashboard de algoritmos probabilísticos
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Hashing, QuickSort, Bloom filter, momentos de frecuencia y PageRank sobre
            {data ? ` ${data.meta.videos.toLocaleString()} videos y ${data.meta.categories} categorías` : " el dataset de videos"}.
          </p>
        </div>
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
              ? `Actualizado ${lastUpdated.toLocaleTimeString()}`
              : "Conectando…"}
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          No se pudo contactar <code className="font-mono">{API_URL}</code>. Inicia la API con{" "}
          <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono">
            py analytics/aggregate_api.py --serve 8000
          </code>
          {data && " — mostrando los últimos datos recibidos."}
        </div>
      )}

      {!data ? (
        <div className="grid gap-5 lg:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-96 animate-pulse rounded-2xl border border-white/10 bg-slate-900/50" />
          ))}
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          <BucketDistributionChart data={data.panel_a_bucket_load} />
          <RuntimeChart data={data.panel_b_runtimes} />
          <LiveMetricsPanel data={data.panel_c_realtime} ticks={ticks} />
          <PageRankPanel data={data.panel_d_pagerank} />
        </div>
      )}

      <footer className="mt-8 text-center text-[11px] text-slate-500">
        Datos: Arley (pipelines/matrices) + Juan Camilo (algoritmos probabilísticos) · refresco cada 5 s
      </footer>
    </main>
  );
}
