"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData } from "@/lib/types";
import { axisProps, ChartTooltip, COLORS, Panel, Stat } from "./ui";

type Props = { data: DashboardData["panel_h_threshold_outcome"] };

const pct = (v: number, d = 2) => `${(v * 100).toFixed(d)}%`;

export default function LshThresholdOutcomePanel({ data }: Props) {
  const [tab, setTab] = useState<"threshold" | "outcome">("threshold");
  const lsh = data.threshold_lsh;
  const out = data.outcome_test;

  const outcomeRows = out.groups.map((g) => ({
    ...g,
    mean_pct: Number((g.mean_neighbor_flagged_frac * 100).toFixed(2)),
    pct_flagged_neighbors: Number((g.pct_neighbors_flagged * 100).toFixed(1)),
  }));

  return (
    <Panel
      id="panel-h"
      tag="H"
      title="S25 Threshold Design (MinHash/LSH) & Outcome Test (W5)"
      subtitle={`MinHash n=${lsh.n_hashes} en MapReduce U4 (${lsh.mapreduce_runner_metrics.num_workers} workers) · Diseño (b=${lsh.selected_b}, r=${lsh.selected_r}) y prueba de señal flagged_frac.`}
      action={
        <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
          <button
            onClick={() => setTab("threshold")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "threshold" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            S25 Umbral & P/R (T4)
          </button>
          <button
            onClick={() => setTab("outcome")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "outcome" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Outcome Test flagged_frac (T5)
          </button>
        </div>
      }
    >
      {tab === "threshold" ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label={`Diseño (b=${lsh.selected_b}, r=${lsh.selected_r})`}
              value={`t = ${lsh.theoretical_threshold_t.toFixed(2)}`}
              hint={`FNR(0.8): teór ${pct(lsh.theoretical_fnr_s08)} · emp ${pct(lsh.empirical_fnr_s08)}`}
              tone="good"
            />
            <Stat
              label="Precisión / Recall (s≥0.6)"
              value={`${pct(lsh.precision, 1)} / ${pct(lsh.recall, 1)}`}
              hint={`TP=${lsh.true_positives} · FP=${lsh.false_positives} · FN=${lsh.false_negatives}`}
              tone="good"
            />
            <Stat
              label="Pares Candidatos"
              value={lsh.candidate_pairs.toLocaleString()}
              hint={`vs ${lsh.total_pairs.toLocaleString()} totales`}
            />
            <Stat
              label="Comparaciones Ahorradas"
              value={`${lsh.comparisons_saved_pct.toFixed(2)}%`}
              hint={`MR U4: ${lsh.mapreduce_runner_metrics.wall_time_ms.toFixed(0)} ms`}
              tone="good"
            />
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-1 text-xs font-semibold text-slate-200">
                Curva S de LSH: P(candidato | s) = 1 − (1 − sʳ)ᵇ
              </h4>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lsh.s_curve} margin={{ top: 8, right: 12, left: -10, bottom: 6 }}>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="s" {...axisProps} />
                    <YAxis {...axisProps} domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip content={<ChartTooltip labelPrefix="Jaccard s = " format={(p) => pct(Number(p.value), 1)} />} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <ReferenceLine x={0.6} stroke="#f59e0b" strokeDasharray="3 3" />
                    <ReferenceLine x={0.8} stroke="#34d399" strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="b25_r4" name="b=25, r=4" stroke="#64748b" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="b20_r5" name="b=20, r=5 ★" stroke={COLORS.twoChoices} strokeWidth={3} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="b16_r6" name="b=16, r=6" stroke={COLORS.pagerank} strokeWidth={1.8} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="b10_r10" name="b=10, r=10" stroke={COLORS.chaining} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-1 text-xs font-semibold text-slate-200">
                Validación Empírica vs Fuerza Bruta ({lsh.total_pairs.toLocaleString()} pares)
              </h4>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={lsh.pr_sweep.map((p) => ({
                      ...p,
                      prec_pct: Number((p.precision * 100).toFixed(1)),
                      rec_pct: Number((p.recall * 100).toFixed(1)),
                    }))}
                    margin={{ top: 8, right: 12, left: -10, bottom: 6 }}
                  >
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="config" {...axisProps} fontSize={10} />
                    <YAxis {...axisProps} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
                    <Tooltip content={<ChartTooltip format={(p) => `${Number(p.value).toFixed(1)}%`} />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="prec_pct" name="Precisión (%)" fill={COLORS.pagerank} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                    <Bar dataKey="rec_pct" name="Recall (%)" fill={COLORS.randomized} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Diseño (b, r)</th>
                  <th>Umbral t</th>
                  <th>P(s=0.6)</th>
                  <th>FNR(s=0.8)</th>
                  <th>Candidatos Emp.</th>
                  <th>Cumple FNR≤1%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {lsh.design_table.map((d) => {
                  const emp = lsh.pr_sweep.find((x) => x.b === d.b && x.r === d.r);
                  return (
                    <tr key={`${d.b}_${d.r}`} className={d.selected ? "bg-cyan-500/10" : ""}>
                      <td className="py-1 font-bold text-slate-100">
                        ({d.b}, {d.r}) {d.selected ? "★" : ""}
                      </td>
                      <td>{d.threshold_t.toFixed(3)}</td>
                      <td className="text-cyan-300">{pct(d.prob_s_06, 1)}</td>
                      <td className={d.meets_fnr_1pct ? "text-emerald-300" : "text-rose-300"}>
                        {pct(d.fnr_s_08, 3)}
                      </td>
                      <td>{emp ? emp.candidate_pairs.toLocaleString() : "—"}</td>
                      <td className={d.meets_fnr_1pct ? "text-emerald-400" : "text-rose-400"}>
                        {d.meets_fnr_1pct ? "SÍ ✓" : "NO ✗"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Lift MinHash vs Azar"
              value={`${out.minhash_lift_vs_random.toFixed(2)}×`}
              hint="Vecinos de cuentas marcadas"
              tone="alert"
            />
            <Stat
              label="Lift Cosine vs Azar"
              value={`${out.cosine_lift_vs_random.toFixed(2)}×`}
              hint="Cosine LSH (sin flagged_frac)"
            />
            <Stat
              label="Estadístico z"
              value={`z = ${out.z_statistic.toFixed(1)}`}
              hint={out.p_value < 1e-12 ? "p < 1e-12 (Altamente sig.)" : `p = ${out.p_value.toExponential(2)}`}
              tone="good"
            />
            <Stat
              label="Cuentas Marcadas"
              value={out.flagged_accounts_count}
              hint={`Umbral ≥ ${(out.flagged_threshold * 100).toFixed(0)}% · Excluido del vector`}
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-1 text-xs font-semibold text-slate-200">
              Outcome Test: flagged_frac Promedio de los Top-5 Vecinos vs 5 Uploaders Aleatorios
            </h4>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={outcomeRows} margin={{ top: 8, right: 16, left: -4, bottom: 8 }}>
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="short_label" {...axisProps} fontSize={10} />
                  <YAxis {...axisProps} unit="%" />
                  <Tooltip content={<ChartTooltip format={(p) => `${Number(p.value).toFixed(2)}%`} />} />
                  <Bar dataKey="mean_pct" name="flagged_frac promedio vecinos (%)" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                    {outcomeRows.map((row, idx) => (
                      <Cell
                        key={row.short_label}
                        fill={idx === 0 ? COLORS.alert : idx === 1 ? COLORS.deterministic : idx === 2 ? COLORS.twoChoices : "#64748b"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Cohorte evaluada</th>
                  <th>Media flagged_frac vecinos</th>
                  <th>% Vecinos marcados (≥25%)</th>
                  <th>Lift vs Azar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {out.groups.map((g, i) => (
                  <tr key={g.group} className={i === 0 ? "bg-rose-500/10" : ""}>
                    <td className="py-1 font-sans text-slate-200">{g.group}</td>
                    <td className={i === 0 ? "font-bold text-rose-300" : "text-slate-200"}>
                      {pct(g.mean_neighbor_flagged_frac, 2)}
                    </td>
                    <td className="text-cyan-300">{pct(g.pct_neighbors_flagged, 1)}</td>
                    <td className={g.lift_vs_random > 2 ? "font-bold text-emerald-300" : "text-slate-400"}>
                      {g.lift_vs_random.toFixed(2)}×
                    </td>
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

