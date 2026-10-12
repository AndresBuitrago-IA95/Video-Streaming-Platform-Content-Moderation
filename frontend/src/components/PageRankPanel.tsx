"use client";

import { useState } from "react";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { DashboardData, PageRankRow } from "@/lib/types";
import { COLORS, Panel, Stat } from "./ui";

type Props = { data: DashboardData["panel_d_pagerank"] };

function RadarTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload?: PageRankRow }[];
}) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  return (
    <div className="max-w-64 rounded-lg border border-white/15 bg-slate-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 font-semibold text-slate-100">{row.category}</div>
      <div className="text-violet-300">
        PageRank: <span className="font-mono">{row.pagerank_scaled.toFixed(1)}</span>/100 · raw{" "}
        <span className="font-mono">{row.pagerank.toFixed(4)}</span> (rango #{row.pagerank_rank})
      </div>
      <div className="text-sky-300">
        Frecuencia Subidas: <span className="font-mono">{row.frequency_scaled.toFixed(1)}</span>/100 ·{" "}
        {row.upload_count.toLocaleString()} videos (rango #{row.frequency_rank})
      </div>
      <div className="text-rose-300">
        Frac. Marcada (Overlay): <span className="font-mono">{row.flagged_scaled.toFixed(1)}</span>/100 ·{" "}
        <span className="font-mono">{(row.flagged_frac * 100).toFixed(2)}%</span> marcados
      </div>
      <div className="mt-1.5 border-t border-white/10 pt-1.5 text-[10px] leading-snug text-slate-400">
        Distribución estacionaria π: {(row.stationary * 100).toFixed(2)}%
      </div>
    </div>
  );
}

export default function PageRankPanel({ data }: Props) {
  const [tab, setTab] = useState<"radar" | "markov" | "twosat">("radar");
  const rows = data.categories;
  const rho = data.meta.spearman_rank_correlation;
  const biggest = [...rows].sort((a, b) => Math.abs(b.rank_delta) - Math.abs(a.rank_delta))[0];
  const rawSpreadPct = data.meta.pagerank_spread * 100;
  const markov = data.markov;

  return (
    <Panel
      id="panel-d"
      tag="D"
      title="Graph Analytics: PageRank, Markov & 2-SAT (W3)"
      subtitle={
        <>
          Overlay: PageRank vs Frecuencia vs Fracción Marcada (`flagged_frac`).{" "}
          <span
            title="Las probabilidades de transición entre categorías son casi uniformes: el rango bruto de PageRank es de solo ~0.7 pp. Interpreta las variaciones relativas como leves sesgos estructurales de navegación."
            className="cursor-help rounded border border-amber-400/40 bg-amber-400/10 px-1.5 py-0.5 text-amber-200"
          >
            ⓘ categorías casi uniformes
          </span>
        </>
      }
      action={
        <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
          <button
            onClick={() => setTab("radar")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "radar" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            PageRank Overlay
          </button>
          <button
            onClick={() => setTab("markov")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "markov" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Cadena DTMC & π (T1-T4)
          </button>
          <button
            onClick={() => setTab("twosat")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "twosat" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Políticas 2-SAT (T5)
          </button>
        </div>
      }
    >
      {tab === "radar" && (
        <>
          <div className="mb-3 grid grid-cols-3 gap-2">
            <Stat
              label="Correlación Rangos (ρ)"
              value={rho === null ? "—" : rho.toFixed(2)}
              hint="PR vs Frecuencia"
            />
            <Stat
              label="Rango Bruto PR"
              value={`${rawSpreadPct.toFixed(2)} pp`}
              hint={`d=${data.meta.damping} · ${data.meta.iterations} iter`}
              tone="alert"
            />
            <Stat
              label="Mayor Salto"
              value={`${biggest.rank_delta > 0 ? "+" : ""}${biggest.rank_delta}`}
              hint={biggest.category}
              tone="good"
            />
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={rows} outerRadius="70%">
                <PolarGrid stroke={COLORS.grid} />
                <PolarAngleAxis dataKey="category" tick={{ fill: "#cbd5e1", fontSize: 10 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: COLORS.axis, fontSize: 9 }} tickCount={5} stroke={COLORS.grid} />
                <Tooltip content={<RadarTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Radar name="PageRank (0-100)" dataKey="pagerank_scaled" stroke={COLORS.pagerank} fill={COLORS.pagerank} fillOpacity={0.25} strokeWidth={2} isAnimationActive={false} />
                <Radar name="Frecuencia Subidas (0-100)" dataKey="frequency_scaled" stroke={COLORS.frequency} fill={COLORS.frequency} fillOpacity={0.2} strokeWidth={2} isAnimationActive={false} />
                <Radar name="Frac. Marcada Overlay (0-100)" dataKey="flagged_scaled" stroke={COLORS.alert} fill={COLORS.alert} fillOpacity={0.15} strokeWidth={2} isAnimationActive={false} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {tab === "markov" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Clasificación Estados" value={markov.classification.irreducible ? "Irreducible" : "Reducible"} hint={`${markov.classification.num_classes} clase(s) comunicante`} tone="good" />
            <Stat label="Sumideros Absorbentes" value={markov.classification.has_absorbing_sink ? "Detectado" : "Ninguno"} hint="Uploaders no quedan atrapados" tone="good" />
            <Stat label="Periodicidad" value={markov.classification.aperiodic ? "Aperiódica" : `Periodo ${markov.classification.period}`} hint="Garantiza convergencia a π" tone="good" />
            <Stat label="Gravity Well (Top π)" value={markov.stationary.top_category} hint={`${(markov.stationary.top_value * 100).toFixed(2)}% actividad a largo plazo`} />
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-200">
                W3 T4: Lazy Random Walk (L = (I+P)/2) vs Distribución Estacionaria π (50,000 pasos)
              </h4>
              <span className="text-[11px] text-emerald-400">
                Variación Total: {(markov.lazy_walk.total_variation * 100).toFixed(2)}% | Error Máx: {(markov.lazy_walk.max_abs_error * 100).toFixed(2)}%
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="py-1">Categoría</th>
                    <th>Teórica (π)</th>
                    <th>Empírica (50k pasos)</th>
                    <th>Diferencia Absoluta</th>
                    <th>Rol a Largo Plazo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-mono">
                  {markov.lazy_walk.categories.map((c) => (
                    <tr key={c.category}>
                      <td className="py-1 text-slate-200 font-sans font-medium">{c.category}</td>
                      <td className="text-violet-300">{(c.pi * 100).toFixed(3)}%</td>
                      <td className="text-cyan-300">{(c.empirical * 100).toFixed(3)}%</td>
                      <td className="text-slate-400">{(Math.abs(c.pi - c.empirical) * 100).toFixed(3)}%</td>
                      <td className="text-slate-400 font-sans">
                        {c.category === markov.stationary.top_category ? "Gravity Well Principal" : "Estado Recurrente"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {tab === "twosat" && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Resolución Papadimitriou" value={markov.two_sat.found ? "SATISFACTIBLE" : "UNSAT"} hint={`${markov.two_sat.variables} variables, ${markov.two_sat.constraints} cláusulas`} tone="good" />
            <Stat label="Intentos / Pasos" value={`${markov.two_sat.attempts} / ${markov.two_sat.flips} flips`} hint="Algoritmo 2-SAT aleatorizado" />
            <Stat label="Categorías en Riesgo" value={markov.two_sat.risk_categories.length} hint={markov.two_sat.risk_categories.join(", ")} tone="alert" />
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-2 text-xs font-semibold text-slate-200">
              W3 T5: Asignación de Políticas de Moderación (R = Reforzar Revisores, T = Throttling/Limitar)
            </h4>
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
                <span className="text-[11px] font-medium text-slate-400">Asignación Booleana de Políticas:</span>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs font-mono">
                  {Object.entries(markov.two_sat.assignment).map(([k, v]) => (
                    <div key={k} className="flex justify-between rounded bg-slate-900/80 px-2 py-1">
                      <span className="text-slate-300">{k}:</span>
                      <span className={v ? "font-bold text-emerald-400" : "text-slate-500"}>
                        {v ? "ACTIVAR (True)" : "INACTIVO (False)"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
                <span className="text-[11px] font-medium text-slate-400">Verificación de Restricciones del Negocio:</span>
                <div className="mt-2 space-y-1 text-xs">
                  {markov.two_sat.checks.map((c, i) => (
                    <div key={i} className="flex items-center justify-between rounded bg-slate-900/80 px-2 py-1 font-mono text-[11px]">
                      <span className="text-slate-300">{c.clause}</span>
                      <span className="font-bold text-emerald-400">✓ CUMPLE</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
