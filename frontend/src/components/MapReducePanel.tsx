"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData } from "@/lib/types";
import { axisProps, ChartTooltip, COLORS, Panel, Stat } from "./ui";

type Props = { data: DashboardData["panel_e_mapreduce"] };

const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;

export default function MapReducePanel({ data }: Props) {
  const [tab, setTab] = useState<"efficiency" | "shuffle" | "reducers">("efficiency");

  const { s14_skew_mitigation: s14, cost_analysis: cost, reducer_analysis: red, pipeline_validation: val } = data;
  const p8 = s14.summary_p8;
  const row1x = cost.scaling_rows[0];
  const row10x = cost.scaling_rows[cost.scaling_rows.length - 1];

  const effRows = s14.rows.map((r) => ({
    ...r,
    skewed_eff_pct: Number((r.skewed_efficiency * 100).toFixed(1)),
    mitigated_eff_pct: Number((r.mitigated_efficiency * 100).toFixed(1)),
  }));

  const shuffleRows = cost.scaling_rows.map((r) => ({
    scale: r.scale,
    sin_combiner_k: Number((r.no_combiner_pairs / 1000).toFixed(1)),
    con_combiner_k: Number((r.with_combiner_pairs / 1000).toFixed(1)),
    job1b_sin_k: Number((r.job1b_no_combiner_pairs / 1000).toFixed(1)),
    job1b_con_k: Number((r.job1b_with_combiner_pairs / 1000).toFixed(2)),
    reduction_pct: r.total_pairs_reduction_pct,
  }));

  return (
    <Panel
      id="panel-e"
      tag="E"
      title="MapReduce: Eficiencia Paralela & Shuffle (W4)"
      subtitle={`Pipeline sobre ${val.scale_100k_metrics.uploads.toLocaleString()} uploads en ${val.scale_100k_metrics.fragments} fragmentos · S14 ola de spam (${(s14.hot_category_share * 100).toFixed(1)}% en ${s14.hot_category}) y mitigación Salting + Combiner.`}
      action={
        <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
          <button
            onClick={() => setTab("efficiency")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "efficiency" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Speedup & S14 (T5)
          </button>
          <button
            onClick={() => setTab("shuffle")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "shuffle" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Shuffle & Costo (T3)
          </button>
          <button
            onClick={() => setTab("reducers")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "reducers" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Reducers q & r (T4)
          </button>
        </div>
      }
    >
      {tab === "efficiency" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Load Balance (P=8) Skew"
              value={`×${p8.skewed_load_balance.toFixed(2)}`}
              hint={`Hot key: ${s14.hot_category} (${pct(s14.hot_category_share)})`}
              tone="alert"
            />
            <Stat
              label="Load Balance Mitigado"
              value={`×${p8.mitigated_load_balance.toFixed(2)}`}
              hint={`−${p8.lbf_reduction_pct.toFixed(1)}% desbalance`}
              tone="good"
            />
            <Stat
              label="Aceleración P=8 vs Base"
              value={`${p8.mitigated_abs_speedup_vs_base.toFixed(1)}×`}
              hint={`Sin mitigar: ${p8.skewed_speedup.toFixed(2)}×`}
              tone="good"
            />
            <Stat
              label="Reducción Shuffle S14"
              value={`${p8.shuffle_reduction_pct.toFixed(2)}%`}
              hint="Salting + Combiner local"
              tone="good"
            />
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-1 text-xs font-semibold text-slate-200">
                Speedup S(P) vs Workers (P = 1, 2, 4, 8)
              </h4>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={effRows} margin={{ top: 8, right: 12, left: -8, bottom: 8 }}>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="P" {...axisProps} tickFormatter={(v: number) => `P=${v}`} />
                    <YAxis {...axisProps} tickFormatter={(v: number) => `${v}×`} />
                    <Tooltip
                      content={
                        <ChartTooltip
                          labelPrefix="Workers P="
                          format={(p) => `${Number(p.value).toFixed(2)}×`}
                        />
                      }
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="ideal_speedup" name="Ideal (S=P)" stroke="#64748b" strokeDasharray="4 4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="mitigated_speedup" name="Mitigado (Salting+Comb)" stroke={COLORS.randomized} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                    <Line type="monotone" dataKey="skewed_speedup" name="Sesgado (≥40% spam)" stroke={COLORS.chaining} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-1 text-xs font-semibold text-slate-200">
                Eficiencia Paralela E(P) = S(P)/P y Load Balance Factor
              </h4>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={effRows} margin={{ top: 8, right: 12, left: -8, bottom: 8 }}>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="P" {...axisProps} tickFormatter={(v: number) => `P=${v}`} />
                    <YAxis {...axisProps} tickFormatter={(v: number) => `${v}%`} />
                    <Tooltip
                      content={
                        <ChartTooltip
                          labelPrefix="Workers P="
                          format={(p) => `${Number(p.value).toFixed(1)}%`}
                        />
                      }
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="skewed_eff_pct" name="Eficiencia Sesgada (%)" fill={COLORS.chaining} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                    <Bar dataKey="mitigated_eff_pct" name="Eficiencia Mitigada (%)" fill={COLORS.twoChoices} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">P</th>
                  <th>T Sesgado</th>
                  <th>T Mitigado</th>
                  <th>LBF Sesgado</th>
                  <th>LBF Mitigado</th>
                  <th>Speedup Abs.</th>
                  <th>Shuffle Mitigado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {s14.rows.map((r) => (
                  <tr key={r.P}>
                    <td className="py-1 font-bold text-violet-300">P={r.P}</td>
                    <td className="text-rose-300">{r.skewed_time_ms.toFixed(1)} ms</td>
                    <td className="text-emerald-300">{r.mitigated_time_ms.toFixed(1)} ms</td>
                    <td className="text-rose-300">×{r.skewed_load_balance.toFixed(2)}</td>
                    <td className="text-emerald-300">×{r.mitigated_load_balance.toFixed(2)}</td>
                    <td className="text-cyan-300">{r.mitigated_abs_speedup_vs_base.toFixed(2)}×</td>
                    <td className="text-slate-300">{r.mitigated_shuffle_pairs.toLocaleString()} pares</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "shuffle" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Reducción Total (1x)"
              value={`−${row1x.total_pairs_reduction_pct.toFixed(1)}%`}
              hint={`Job 1b: −${row1x.job1b_reduction_pct.toFixed(1)}%`}
              tone="good"
            />
            <Stat
              label="Linealidad R²"
              value={cost.linearity.r2_no_combiner_pairs.toFixed(5)}
              hint={`2x/1x = ${cost.linearity.ratio_2x_to_1x_no_combiner.toFixed(2)} · 4x/1x = ${cost.linearity.ratio_4x_to_1x_no_combiner.toFixed(2)}`}
              tone="good"
            />
            <Stat
              label="Extrapolación 10x (1M)"
              value={`${(row10x.with_combiner_pairs / 1e6).toFixed(2)}M`}
              hint={`Sin combiner: ${(row10x.no_combiner_pairs / 1e6).toFixed(2)}M pares`}
            />
            <Stat
              label="Costo S10 PageRank"
              value={`${cost.s10_cost.total_pairs.toLocaleString()}`}
              hint={`${cost.s10_cost.pairs_per_iteration} pares/iter × ${cost.s10_cost.iterations} iter`}
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-1 text-xs font-semibold text-slate-200">
              Tamaño de Shuffle (Miles de pares K-V): Sin Combiner vs Con Combiner (1x, 2x, 4x y 10x extrapolado)
            </h4>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={shuffleRows} margin={{ top: 8, right: 12, left: -4, bottom: 8 }}>
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="scale" {...axisProps} />
                  <YAxis {...axisProps} tickFormatter={(v: number) => `${v}k`} />
                  <Tooltip
                    content={
                      <ChartTooltip format={(p) => `${Number(p.value).toLocaleString()}k pares`} />
                    }
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="sin_combiner_k" name="Sin Combiner (Total)" fill={COLORS.chaining} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="con_combiner_k" name="Con Combiner (Total)" fill={COLORS.twoChoices} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Escala</th>
                  <th>Uploads</th>
                  <th>Sin Combiner</th>
                  <th>Con Combiner</th>
                  <th>Job 1b (Con Comb.)</th>
                  <th>Ahorro Bytes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {cost.scaling_rows.map((r) => (
                  <tr key={r.scale} className={r.extrapolated ? "bg-violet-500/10" : ""}>
                    <td className="py-1 font-sans font-semibold text-slate-200">{r.scale}</td>
                    <td>{r.uploads.toLocaleString()}</td>
                    <td className="text-rose-300">{r.no_combiner_pairs.toLocaleString()}</td>
                    <td className="text-cyan-300">{r.with_combiner_pairs.toLocaleString()}</td>
                    <td className="text-emerald-300">{r.job1b_with_combiner_pairs.toLocaleString()} (−{r.job1b_reduction_pct.toFixed(1)}%)</td>
                    <td className="text-emerald-300">−{r.total_bytes_reduction_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "reducers" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat
              label="Hot Key (Job 1)"
              value={red.hot_key_uploader}
              hint={`q_hotkey = ${red.hot_key_upload_count.toLocaleString()} uploads`}
              tone="alert"
            />
            <Stat
              label="Carga Máx. R=1 → R=8"
              value={`${red.reducer_sweep[0].max_reducer_load.toLocaleString()} → ${red.reducer_sweep[red.reducer_sweep.length - 1].max_reducer_load.toLocaleString()}`}
              hint="Efecto de paralelizar reducers"
              tone="good"
            />
            <Stat
              label="Balance en R=8"
              value={`×${red.reducer_sweep[red.reducer_sweep.length - 1].load_balance_factor.toFixed(2)}`}
              hint="max_load / mean_load"
            />
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-1 text-xs font-semibold text-slate-200">
              Job 1 (100k uploads): Carga Máxima por Reducer vs Número de Reduce Tasks (R = 1, 2, 4, 8)
            </h4>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={red.reducer_sweep} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="R" {...axisProps} tickFormatter={(v: number) => `R=${v}`} />
                  <YAxis {...axisProps} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip content={<ChartTooltip labelPrefix="R=" format={(p) => `${Number(p.value).toLocaleString()} registros`} />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="max_reducer_load" name="Carga Máxima (q)" fill={COLORS.pagerank} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="mean_reducer_load" name="Carga Media (N/R)" fill={COLORS.frequency} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-950/40 p-2.5">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400">
                  <th className="py-1">Job MapReduce</th>
                  <th>Clave</th>
                  <th>Replicación (r)</th>
                  <th>Tamaño Reducer (q)</th>
                  <th>Hot Key</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {red.jobs_rq.map((j) => (
                  <tr key={j.job}>
                    <td className="py-1 font-medium text-slate-200">{j.job}</td>
                    <td className="font-mono text-slate-400">{j.key}</td>
                    <td className="font-mono text-cyan-300">{j.replication_rate_r.toFixed(3)}</td>
                    <td className="font-mono text-violet-300">{j.max_reducer_size_q.toLocaleString()}</td>
                    <td className="font-mono text-slate-300">{j.hot_key} ({j.hot_key_count})</td>
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

