"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { CategoryNodeSummary, DashboardData } from "@/lib/types";
import { axisProps, COLORS, Panel, Stat } from "./ui";

type Props = { data: DashboardData["panel_f_category_flow"] };

const pct = (v: number, d = 2) => `${(v * 100).toFixed(d)}%`;

function FlowTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: readonly { payload?: CategoryNodeSummary }[];
}) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  return (
    <div className="max-w-64 rounded-lg border border-white/15 bg-slate-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 flex items-center justify-between gap-2 font-semibold text-slate-100">
        <span>{row.category}</span>
        <span className={row.growing && row.high_flag ? "text-rose-400" : "text-cyan-300"}>
          {row.net_flow >= 0 ? `+${row.net_flow}` : row.net_flow} flujo
        </span>
      </div>
      <div className="text-slate-300">
        Tasa Marcados: <span className="font-mono text-rose-300">{pct(row.flagged_frac)}</span>
      </div>
      <div className="text-slate-300">
        Entradas / Salidas: <span className="font-mono">{row.in_transition_count.toLocaleString()}</span> /{" "}
        <span className="font-mono">{row.out_transition_count.toLocaleString()}</span>
      </div>
      <div className="text-slate-300">
        Vistas 1h promedio: <span className="font-mono">{row.avg_view_count_1h.toLocaleString()}</span>
      </div>
      <div className="mt-1 border-t border-white/10 pt-1 text-[10px] text-slate-400">{row.quadrant}</div>
    </div>
  );
}

export default function CategoryFlowPanel({ data }: Props) {
  const [tab, setTab] = useState<"flow" | "s10">("flow");
  const nodes = data.node_summary_100k;
  const meanFlag = data.mean_flagged_frac;
  const highRiskGrowing = nodes.filter((n) => n.growing && n.high_flag);
  const val = data.unit3_edge_validation;
  const s10 = data.s10_pagerank_mr;

  const scatterData = nodes.map((n) => ({
    ...n,
    flagged_pct: Number((n.flagged_frac * 100).toFixed(2)),
  }));

  return (
    <Panel
      id="panel-f"
      tag="F"
      title="Node Summary: Net Flow vs Flagged Rate (W4)"
      subtitle="Categorías en crecimiento (net_flow > 0) con alta tasa de marcados + validación MapReduce vs Unidad 3."
      action={
        <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
          <button
            onClick={() => setTab("flow")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "flow" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Flujo Neto & Flag (T1/T6)
          </button>
          <button
            onClick={() => setTab("s10")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "s10" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Validación S10 PageRank (T2)
          </button>
        </div>
      }
    >
      {tab === "flow" ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Validación Job 1 vs U3"
              value={val.passed ? "EXACTO ✓" : "DIF"}
              hint={`${val.edges_checked} aristas · ${val.transition_count_mismatches} errores`}
              tone={val.passed ? "good" : "alert"}
            />
            <Stat
              label="S10 MR vs U3 PageRank"
              value={s10.within_1e4 ? `< 1e-4 ✓` : "REVISAR"}
              hint={`máx Δ = ${s10.max_abs_diff_vs_unit3.toExponential(1)}`}
              tone={s10.within_1e4 ? "good" : "alert"}
            />
            <Stat
              label="Crecientes + Alto Flag"
              value={highRiskGrowing.length}
              hint={highRiskGrowing.map((x) => x.category).join(", ") || "Ninguna"}
              tone={highRiskGrowing.length > 0 ? "alert" : "default"}
            />
            <Stat
              label="Media flagged_frac"
              value={pct(meanFlag)}
              hint="Σ net_flow = 0 (conservación)"
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <div className="mb-1 flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-200">
                Cuadrante de Riesgo: Flujo Neto (in − out) vs Tasa de Marcados (%)
              </h4>
              <span className="text-[11px] text-rose-300">● Cuadrante superior derecho = Creciendo con alto flag</span>
            </div>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 16, left: -4, bottom: 16 }}>
                  <CartesianGrid stroke={COLORS.grid} />
                  <XAxis
                    type="number"
                    dataKey="net_flow"
                    name="Net Flow"
                    {...axisProps}
                    label={{ value: "Flujo neto (in_transition_count − out_transition_count)", position: "insideBottom", offset: -8, fill: COLORS.axis, fontSize: 11 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="flagged_pct"
                    name="Flagged %"
                    {...axisProps}
                    unit="%"
                    domain={["auto", "auto"]}
                  />
                  <ZAxis type="number" dataKey="in_transition_count" range={[70, 260]} name="Entradas" />
                  <ReferenceLine x={0} stroke="#64748b" strokeDasharray="4 4" />
                  <ReferenceLine y={Number((meanFlag * 100).toFixed(2))} stroke="#f43f5e" strokeDasharray="4 4" />
                  <Tooltip content={<FlowTooltip />} cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter name="Categorías" data={scatterData} isAnimationActive={false}>
                    {scatterData.map((row) => (
                      <Cell
                        key={row.category}
                        fill={
                          row.growing && row.high_flag
                            ? COLORS.alert
                            : row.growing
                              ? COLORS.twoChoices
                              : row.high_flag
                                ? COLORS.deterministic
                                : COLORS.pagerank
                        }
                      />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Categoría</th>
                  <th>Salidas (out)</th>
                  <th>Entradas (in)</th>
                  <th>Net Flow</th>
                  <th>Flagged Frac</th>
                  <th>Vistas 1h</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {nodes.map((n) => (
                  <tr key={n.category} className={n.growing && n.high_flag ? "bg-rose-500/10" : ""}>
                    <td className="py-1 font-sans font-medium text-slate-200">{n.category}</td>
                    <td>{n.out_transition_count.toLocaleString()}</td>
                    <td>{n.in_transition_count.toLocaleString()}</td>
                    <td className={n.net_flow >= 0 ? "text-emerald-300" : "text-slate-400"}>
                      {n.net_flow >= 0 ? `+${n.net_flow}` : n.net_flow}
                    </td>
                    <td className={n.high_flag ? "text-rose-300 font-bold" : "text-slate-300"}>
                      {pct(n.flagged_frac)}
                    </td>
                    <td className="text-slate-400">{n.avg_view_count_1h.toLocaleString()}</td>
                    <td className="font-sans text-[11px]">
                      <span
                        className={`rounded px-1.5 py-0.5 ${
                          n.growing && n.high_flag
                            ? "bg-rose-500/20 text-rose-200"
                            : n.growing
                              ? "bg-cyan-500/15 text-cyan-200"
                              : "bg-white/5 text-slate-400"
                        }`}
                      >
                        {n.growing && n.high_flag ? "Prioridad Alta" : n.growing ? "Creciente" : "Estable/Salida"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Iteraciones S10" value={s10.iterations} hint={`d = ${s10.damping} · tol = 1e-10`} />
            <Stat label="Pares Totales S10" value={s10.total_s10_pairs.toLocaleString()} hint={`${s10.pairs_per_iteration} pares/iter`} />
            <Stat
              label="Error Máx vs U3"
              value={s10.max_abs_diff_vs_unit3.toExponential(2)}
              hint="Requisito: < 1e-4"
              tone={s10.within_1e4 ? "good" : "alert"}
            />
            <Stat label="Validación S10" value={s10.within_1e4 ? "APROBADO ✓" : "FALLÓ"} hint={`q = ${s10.max_reducer_load_q} · r = ${s10.replication_rate_r.toFixed(1)}`} tone="good" />
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-2 text-xs font-semibold text-slate-200">
              Comparación PageRank MapReduce (S10) vs PageRank Unidad 3
            </h4>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Categoría</th>
                  <th>PageRank MapReduce (S10)</th>
                  <th>PageRank Unidad 3</th>
                  <th>|Diferencia|</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {s10.comparison.map((row) => (
                  <tr key={row.category}>
                    <td className="py-1 font-sans font-medium text-slate-200">{row.category}</td>
                    <td className="text-violet-300">{row.mr_pagerank.toFixed(6)}</td>
                    <td className="text-cyan-300">{row.unit3_pagerank.toFixed(6)}</td>
                    <td className="text-emerald-400">{row.abs_diff.toExponential(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Panel>
  );
}

