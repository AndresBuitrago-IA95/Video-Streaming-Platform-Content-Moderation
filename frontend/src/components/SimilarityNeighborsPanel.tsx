"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData, NeighborHit } from "@/lib/types";
import { axisProps, ChartTooltip, COLORS, Panel, Stat } from "./ui";

type Props = { data: DashboardData["panel_g_neighbors"] };

const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;

function NeighborColumn({
  title,
  accent,
  candidates,
  rows,
}: {
  title: string;
  accent: string;
  candidates: number;
  rows: NeighborHit[];
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/50 p-2.5">
      <div className="mb-2 flex items-center justify-between border-b border-white/10 pb-1.5">
        <span className={`text-xs font-semibold ${accent}`}>{title}</span>
        <span className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
          {candidates} cand.
        </span>
      </div>
      {rows.length === 0 ? (
        <div className="py-4 text-center text-[11px] text-slate-500">Sin candidatos LSH en bandas</div>
      ) : (
        <div className="space-y-1.5">
          {rows.map((n, idx) => (
            <div
              key={`${title}-${n.uploader_id}`}
              className="flex items-center justify-between rounded-lg bg-white/[0.03] px-2 py-1.5 text-xs"
            >
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[10px] text-slate-500">#{idx + 1}</span>
                  <span className="font-mono font-medium text-slate-100">{n.uploader_id}</span>
                  {n.cluster_id && (
                    <span className="rounded bg-violet-500/20 px-1 text-[9px] text-violet-200">
                      {n.cluster_id}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-[10px] text-slate-400">
                  flagged:{" "}
                  <span className={n.flagged_frac >= 0.25 ? "font-bold text-rose-300" : "text-emerald-300"}>
                    {pct(n.flagged_frac, 1)}
                  </span>
                </div>
              </div>
              <span className="font-mono text-xs font-bold text-cyan-300">{n.score.toFixed(3)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SimilarityNeighborsPanel({ data }: Props) {
  const [tab, setTab] = useState<"neighbors" | "distributions" | "hyperplanes" | "shingles">("neighbors");
  const [selectedUid, setSelectedUid] = useState<string>(data.queries[0]?.uploader_id ?? "");
  const [distMetric, setDistMetric] = useState<"jaccard" | "cosine" | "l1" | "l2">("jaccard");

  const activeQuery = data.queries.find((q) => q.uploader_id === selectedUid) ?? data.queries[0];
  const t1 = data.task1_representations;
  const t2 = data.task2_hyperplanes;
  const t3 = data.task3_k_shingles;

  return (
    <Panel
      id="panel-g"
      tag="G"
      title="Similitud & Top-5 Vecinos por Método (W5)"
      subtitle={`Dataset de ${data.meta.n_uploaders.toLocaleString()} uploaders (${data.meta.planted_clusters} clusters sembrados) · Comparación MinHash/LSH, Cosine LSH y LCS.`}
      action={
        <div className="inline-flex flex-wrap rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
          {(
            [
              ["neighbors", "Top-5 Vecinos (T5)"],
              ["distributions", "Distancias (T1)"],
              ["hyperplanes", "Hiperplanos (T2)"],
              ["shingles", "k-Shingles S21 (T3)"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`rounded px-2 py-1 text-xs font-medium ${
                tab === id ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      }
    >
      {tab === "neighbors" && activeQuery && (
        <div className="space-y-3">
          {/* Selector de uploader */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-slate-950/50 p-2.5">
            <div className="flex items-center gap-2">
              <label htmlFor="w5-uploader-select" className="text-xs font-medium text-slate-300">
                Uploader consulta:
              </label>
              <select
                id="w5-uploader-select"
                value={activeQuery.uploader_id}
                onChange={(e) => setSelectedUid(e.target.value)}
                className="rounded-lg border border-white/15 bg-slate-900 px-2.5 py-1 font-mono text-xs text-slate-100 outline-none focus:border-violet-400"
              >
                {data.queries.map((q) => (
                  <option key={q.uploader_id} value={q.uploader_id}>
                    {q.uploader_id} · flag {pct(q.flagged_frac, 0)}{" "}
                    {q.cluster_id ? `[${q.cluster_id}]` : "[Fondo]"}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span
                className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${
                  activeQuery.is_flagged_account
                    ? "border-rose-400/40 bg-rose-500/15 text-rose-200"
                    : "border-emerald-400/30 bg-emerald-500/10 text-emerald-200"
                }`}
              >
                flagged_frac: {pct(activeQuery.flagged_frac, 1)}
              </span>
              <span className="text-[11px] text-slate-400">
                len={activeQuery.seq_length} · {activeQuery.shingle_count} 3-shingles
              </span>
            </div>
          </div>

          {/* Overlap@5 promedio global y del query */}
          <div className="grid grid-cols-3 gap-2">
            <Stat
              label="Overlap@5 · MH vs Cosine"
              value={pct(activeQuery.overlap_at_5.minhash_vs_cosine, 0)}
              hint={`Media ${data.queries_count} queries: ${pct(data.mean_overlap_at_5.minhash_vs_cosine, 1)}`}
            />
            <Stat
              label="Overlap@5 · MH vs LCS"
              value={pct(activeQuery.overlap_at_5.minhash_vs_lcs, 0)}
              hint={`Media ${data.queries_count} queries: ${pct(data.mean_overlap_at_5.minhash_vs_lcs, 1)}`}
              tone="good"
            />
            <Stat
              label="Overlap@5 · Cosine vs LCS"
              value={pct(activeQuery.overlap_at_5.cosine_vs_lcs, 0)}
              hint={`Media ${data.queries_count} queries: ${pct(data.mean_overlap_at_5.cosine_vs_lcs, 1)}`}
            />
          </div>

          {/* 3 columnas: Top-5 por cada método */}
          <div className="grid gap-2.5 md:grid-cols-3">
            <NeighborColumn
              title="MinHash / LSH (Jaccard)"
              accent="text-violet-300"
              candidates={activeQuery.candidates_examined.minhash_lsh}
              rows={activeQuery.neighbors.minhash_lsh}
            />
            <NeighborColumn
              title="Cosine LSH (Hiperplanos)"
              accent="text-cyan-300"
              candidates={activeQuery.candidates_examined.cosine_lsh}
              rows={activeQuery.neighbors.cosine_lsh}
            />
            <NeighborColumn
              title="LCS Secuencial (Candidatos)"
              accent="text-emerald-300"
              candidates={activeQuery.candidates_examined.lcs_candidates}
              rows={activeQuery.neighbors.unit5_lcs}
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 text-[11px] leading-relaxed text-slate-400">
            <strong className="text-slate-200">Desacuerdos entre métodos:</strong> {data.disagreement_explanation}
          </div>
        </div>
      )}

      {tab === "distributions" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Distribución en {t1.random_pairs_evaluated.toLocaleString()} pares aleatorios · Vector {t1.vector_dim}D (sin{" "}
              <code className="font-mono text-rose-300">{t1.excluded_outcome_field}</code>)
            </span>
            <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
              {(["jaccard", "cosine", "l1", "l2"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setDistMetric(m)}
                  className={`rounded px-2 py-0.5 text-xs uppercase ${
                    distMetric === m ? "bg-violet-600 text-white" : "text-slate-400"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <Stat
              label="Corr. Jaccard–Cosine (500p)"
              value={`r=${t1.correlations_500_pairs.jaccard_vs_cosine.pearson.toFixed(2)}`}
              hint={`Spearman ρ=${t1.correlations_500_pairs.jaccard_vs_cosine.spearman.toFixed(2)}`}
            />
            <Stat
              label="Corr. Jaccard–LCS (500p)"
              value={`r=${t1.correlations_500_pairs.jaccard_vs_lcs.pearson.toFixed(2)}`}
              hint={`Spearman ρ=${t1.correlations_500_pairs.jaccard_vs_lcs.spearman.toFixed(2)}`}
              tone="good"
            />
            <Stat
              label="Corr. Cosine–LCS (500p)"
              value={`r=${t1.correlations_500_pairs.cosine_vs_lcs.pearson.toFixed(2)}`}
              hint={`Spearman ρ=${t1.correlations_500_pairs.cosine_vs_lcs.spearman.toFixed(2)}`}
            />
          </div>

          <div className="h-48 w-full rounded-xl border border-white/10 bg-slate-950/40 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={t1.distributions[distMetric].histogram} margin={{ top: 8, right: 8, left: -12, bottom: 8 }}>
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="label" {...axisProps} interval={2} fontSize={9} />
                <YAxis {...axisProps} />
                <Tooltip content={<ChartTooltip format={(p) => `${Number(p.value).toLocaleString()} pares`} />} />
                <Bar dataKey="count" name={distMetric.toUpperCase()} fill={COLORS.pagerank} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <h4 className="mb-1 text-xs font-semibold text-slate-200">
              Chequeo de Concentración de Distancias (2D vs 10D vs 12D)
            </h4>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Espacio</th>
                  <th>CV L2 (σ/μ)</th>
                  <th>CV L1 (σ/μ)</th>
                  <th>Ratio p95/p5 (L2)</th>
                  <th>Contraste Rel. L2</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {t1.distance_concentration.map((c) => (
                  <tr key={c.space}>
                    <td className="py-1 font-sans text-slate-200">{c.space}</td>
                    <td className="text-cyan-300">{c.l2_cv.toFixed(3)}</td>
                    <td className="text-violet-300">{c.l1_cv.toFixed(3)}</td>
                    <td>{c.l2_p95_p5_ratio.toFixed(2)}×</td>
                    <td className="text-slate-300">{c.l2_rel_contrast_p95.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "hyperplanes" && (
        <div className="space-y-3">
          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-1 text-xs font-semibold text-slate-200">
                Verificación Charikar (n=128): Ángulo Real θ vs Estimado 180·(1−acuerdo)
              </h4>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 8, right: 12, left: -8, bottom: 10 }}>
                    <CartesianGrid stroke={COLORS.grid} />
                    <XAxis type="number" dataKey="true_angle" name="θ real" domain={[0, 180]} {...axisProps} unit="°" />
                    <YAxis type="number" dataKey="estimated_angle" name="θ est." domain={[0, 180]} {...axisProps} unit="°" />
                    <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                    <Scatter name="Pares (n=128)" data={t2.scatter_n128} fill={COLORS.twoChoices} isAnimationActive={false} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-2 text-xs font-semibold text-slate-200">
                Cosine LSH Banding ({t2.queries_evaluated} queries · Recall@5 vs Ahorro)
              </h4>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="py-1">n bits</th>
                    <th>(b, r)</th>
                    <th>MAE θ</th>
                    <th>Recall@5</th>
                    <th>Ahorro</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-mono">
                  {t2.configs.map((c) => (
                    <tr key={c.n_hyperplanes} className={c.n_hyperplanes === 128 ? "bg-violet-500/10" : ""}>
                      <td className="py-1.5 font-bold text-violet-300">{c.n_hyperplanes}</td>
                      <td>({c.bands}, {c.rows_per_band})</td>
                      <td className="text-amber-300">{c.angle_mae_deg.toFixed(1)}°</td>
                      <td className="text-emerald-300 font-bold">{pct(c.recall_at_5, 1)}</td>
                      <td className="text-cyan-300">{pct(c.comparisons_saved_frac, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {tab === "shingles" && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            {t3.rows.map((r) => (
              <Stat
                key={r.k}
                label={`k = ${r.k} Shingles ${r.k === t3.best_k ? "★ Óptimo" : ""}`}
                value={`${r.separation_ratio.toFixed(1)}×`}
                hint={`Intra ${r.intra_cluster_jaccard.toFixed(3)} vs Inter ${r.inter_cluster_jaccard.toFixed(3)}`}
                tone={r.k === t3.best_k ? "good" : "default"}
              />
            ))}
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-1 text-xs font-semibold text-slate-200">
              S21: Separación de Clusters Sembrados (Jaccard Intra-Cluster vs Inter-Cluster)
            </h4>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={t3.rows} margin={{ top: 8, right: 12, left: -8, bottom: 4 }}>
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="k" {...axisProps} tickFormatter={(v: number) => `k=${v}`} />
                  <YAxis {...axisProps} domain={[0, 1]} />
                  <Tooltip content={<ChartTooltip labelPrefix="k=" format={(p) => Number(p.value).toFixed(3)} />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="intra_cluster_jaccard" name="Jaccard Intra-Cluster" fill={COLORS.randomized} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="inter_cluster_jaccard" name="Jaccard Inter-Cluster" fill={COLORS.chaining} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">k</th>
                  <th>Tamaño Medio</th>
                  <th>Posibles (10ᵏ)</th>
                  <th>Observados</th>
                  <th>Cobertura</th>
                  <th>Margen (Intra−Inter)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {t3.rows.map((r) => (
                  <tr key={r.k} className={r.k === t3.best_k ? "bg-emerald-500/10" : ""}>
                    <td className="py-1 font-bold text-violet-300">k={r.k}</td>
                    <td>{r.avg_set_size.toFixed(1)}</td>
                    <td>{r.possible_shingles.toLocaleString()}</td>
                    <td className="text-cyan-300">{r.observed_shingles.toLocaleString()}</td>
                    <td>{r.coverage_pct.toFixed(1)}%</td>
                    <td className="text-emerald-300 font-bold">+{r.separation_margin.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-400">{t3.justification}</p>
        </div>
      )}
    </Panel>
  );
}

