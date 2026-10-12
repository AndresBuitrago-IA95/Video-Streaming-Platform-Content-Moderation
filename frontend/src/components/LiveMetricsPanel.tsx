"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData } from "@/lib/types";
import { axisProps, ChartTooltip, COLORS, Panel, Stat } from "./ui";

type Props = {
  data: DashboardData["panel_c_realtime"];
  ticks: number;
};

const pct = (v: number, d = 2) => `${(v * 100).toFixed(d)}%`;

export default function LiveMetricsPanel({ data, ticks }: Props) {
  const [tab, setTab] = useState<"stream" | "hll" | "reservoir">("stream");
  const [bloomBits, setBloomBits] = useState<number>(8);

  const { live, hll_by_day, reservoir_view_count, chernoff } = data;
  const moments = live.moments;
  const flagRates = live.rolling_flag_rate_by_category;
  const maxRate = Math.max(...flagRates.map((r) => r.flag_rate), 0.01);
  const hllTodayRows = live.distinct_uploaders_today.estimates.map((estimate) => ({
    memory_bits: estimate.memory_bits,
    estimate: estimate.estimate,
    true_count: live.distinct_uploaders_today.true_distinct,
  }));
  const hllBenchmarkRows = hll_by_day.rows.map((row) => ({
    ...row,
    mean_rel_error: row.mean_rel_error * 100,
    theoretical_error: row.theoretical_error * 100,
  }));

  const bloomRow =
    live.bloom_live.find((b) => b.bits_per_element === bloomBits) ??
    live.bloom_live[1] ??
    live.bloom_live[0];

  const windows = live.series.map((w) => ({
    ...w,
    spamF2: w.spam_wave ? w.F2 : null,
  }));

  const isAlert = live.spam.alert;
  const suspicious = chernoff.summary.uploaders_suspicious;

  return (
    <Panel
      id="panel-c"
      tag="C"
      title="Streaming & Métricas Probabilísticas (W2)"
      subtitle={
        <>
          Ventana móvil: últimas {live.window.toLocaleString()} subidas ({live.position} / {live.stream_length}) · tick #{ticks}{" "}
          <span className="ml-1 inline-flex items-center gap-1 text-emerald-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            en vivo (~{live.events_per_second} evt/s)
          </span>
        </>
      }
      action={
        <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
          <button
            onClick={() => setTab("stream")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "stream" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Ventana 1000 & Fk
          </button>
          <button
            onClick={() => setTab("hll")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "hll" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            HyperLogLog (T4)
          </button>
          <button
            onClick={() => setTab("reservoir")}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              tab === "reservoir" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Reservoir Sampling (T3)
          </button>
        </div>
      }
    >
      {/* Alerta de Spam y Chernoff */}
      <div
        id="spam-alert"
        className={`mb-3 flex items-center justify-between rounded-xl border px-3 py-2 text-xs ${
          isAlert
            ? "border-rose-500/50 bg-rose-500/10 text-rose-200"
            : "border-emerald-400/30 bg-emerald-400/5 text-emerald-200"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${isAlert ? "animate-ping bg-rose-400" : "bg-emerald-400"}`} />
          {isAlert ? (
            <span>
              <b>¡Ola de Spam Detectada!</b> z-score $F_2$ = {live.spam.z_F2.toFixed(2)} (umbral {live.spam.threshold}).
              Alta concentración en categoría <b>{moments.top_category}</b> ({pct(moments.top_share, 1)}).
            </span>
          ) : (
            <span>
              <b>Flujo Estable:</b> $F_2$ dentro de rango normal (z = {live.spam.z_F2.toFixed(2)}). Sin anomalías en ventana móvil.
            </span>
          )}
        </div>
        <span className="text-slate-400">
          Chernoff: {suspicious} uploader(s) sospechoso(s) (α={chernoff.summary.alpha})
        </span>
      </div>

      {tab === "stream" && (
        <>
          {/* Métricas de momentos y Bloom */}
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Tasa Marcados (1000)" value={pct(live.overall_flag_rate)} hint="Rolling window W2 T1" />
            <Stat label="F₀ (Categorías)" value={moments.F0} hint={`Top: ${moments.top_category}`} />
            <Stat label="F₁ (Total ventana)" value={moments.F1.toLocaleString()} hint={`Skew: ×${moments.skew_ratio.toFixed(2)}`} />
            <Stat label="F₂ (Momentum)" value={moments.F2.toLocaleString()} hint={`Colisión: ${pct(moments.collision_prob, 2)}`} tone={isAlert ? "alert" : "default"} />
          </div>

          {/* Bloque Bloom Filter */}
          <div className="mb-3 rounded-xl border border-white/10 bg-white/[0.03] p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                Filtro de Bloom · Falsos positivos acumulados hasta la posición {live.position.toLocaleString()} (W2 T2)
              </span>
              <div className="flex gap-1">
                {[4, 8, 12, 16].map((b) => (
                  <button
                    key={b}
                    onClick={() => setBloomBits(b)}
                    className={`rounded px-2 py-0.5 text-xs ${
                      bloomBits === b ? "bg-violet-600 text-white" : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {b} b/item
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-end gap-6 text-xs">
              {bloomRow ? (
                <>
                  <div>
                    <div className="font-mono text-xl font-bold text-cyan-300">
                      {pct(bloomRow.fp_rate_experimental)}
                    </div>
                    <div className="text-[11px] text-slate-400">FP Experimental ({bloomRow.false_positives}/{bloomRow.negatives})</div>
                  </div>
                  <div>
                    <div className="font-mono text-xl font-bold text-violet-300">
                      {pct(bloomRow.fp_rate_theoretical)}
                    </div>
                    <div className="text-[11px] text-slate-400">FP Teórica (k={bloomRow.hash_functions} hashes)</div>
                  </div>
                  <div className="ml-auto text-right text-[11px] text-slate-400">
                    Falsos Negativos
                    <div className="font-mono text-base font-bold text-emerald-400">{bloomRow.false_negatives} (Garantía 0%)</div>
                  </div>
                </>
              ) : (
                <span className="text-xs text-slate-400">Aún no hay elementos para medir.</span>
              )}
            </div>
          </div>

          {/* Gráficos de ventana */}
          <div className="grid gap-3 lg:grid-cols-2">
            <div>
              <h3 className="mb-1 text-xs font-medium text-slate-300">Standing Query: Tasa Marcados por Categoría (1000 vids)</h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={flagRates} layout="vertical" margin={{ top: 4, right: 16, left: 24, bottom: 0 }}>
                    <CartesianGrid stroke={COLORS.grid} horizontal={false} />
                    <XAxis type="number" {...axisProps} tickFormatter={(v: number) => pct(v, 0)} domain={[0, Math.max(maxRate * 1.2, 0.15)]} />
                    <YAxis type="category" dataKey="category" {...axisProps} width={85} />
                    <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} content={<ChartTooltip format={(p) => pct(Number(p.value))} />} />
                    <ReferenceLine x={live.overall_flag_rate} stroke="#e2e8f0" strokeDasharray="3 3" />
                    <Bar dataKey="flag_rate" name="Tasa Marcado" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                      {flagRates.map((r) => (
                        <Cell key={r.category} fill={r.flag_rate > live.overall_flag_rate * 1.15 ? COLORS.alert : COLORS.pagerank} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div>
              <h3 className="mb-1 text-xs font-medium text-slate-300">Serie Temporal F₂ (Detección de Spam Waves)</h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={windows} margin={{ top: 4, right: 12, left: -4, bottom: 0 }}>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="position" {...axisProps} />
                    <YAxis {...axisProps} domain={["auto", "auto"]} />
                    <Tooltip content={<ChartTooltip labelPrefix="Evento " format={(p) => Number(p.value).toLocaleString()} />} />
                    <Line type="monotone" dataKey="F2" name="F₂ Actual" stroke={COLORS.frequency} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="spamF2" name="Ola Spam" stroke="none" dot={{ r: 5, fill: COLORS.alert, stroke: "#fff", strokeWidth: 1 }} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}

      {tab === "hll" && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Consulta Ad-hoc Hoy"
              value={live.distinct_uploaders_today.true_distinct.toLocaleString()}
              hint={`Fecha: ${live.distinct_uploaders_today.date} (Exacto)`}
              tone="good"
            />
            {live.distinct_uploaders_today.estimates.map((est) => (
              <Stat
                key={est.m}
                label={`HLL m=${est.m} (${est.memory_bits} bits)`}
                value={Math.round(est.estimate).toLocaleString()}
                hint={`Error: ${(est.rel_error * 100).toFixed(2)}% (Teór: ${(est.theoretical_error * 100).toFixed(1)}%)`}
              />
            ))}
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-2 text-xs font-semibold text-slate-200">
                Estimación HLL vs. conteo exacto de uploaders de hoy
              </h4>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={hllTodayRows} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="memory_bits" {...axisProps} tickFormatter={(v: number) => `${v} bits`} />
                    <YAxis {...axisProps} allowDecimals={false} />
                    <Tooltip content={<ChartTooltip labelPrefix="Memoria " format={(p) => Number(p.value).toLocaleString()} />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="estimate" name="Estimación HLL" stroke={COLORS.pagerank} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                    <Line type="monotone" dataKey="true_count" name="Conteo exacto" stroke={COLORS.frequency} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
              <h4 className="mb-2 text-xs font-semibold text-slate-200">
                Error relativo vs. memoria (promedio por día)
              </h4>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={hllBenchmarkRows} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
                    <CartesianGrid stroke={COLORS.grid} vertical={false} />
                    <XAxis dataKey="memory_bits" {...axisProps} tickFormatter={(v: number) => `${v} bits`} />
                    <YAxis {...axisProps} tickFormatter={(v: number) => `${v}%`} />
                    <Tooltip content={<ChartTooltip labelPrefix="Memoria " format={(p) => `${Number(p.value).toFixed(2)}%`} />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="mean_rel_error" name="Error empírico" stroke={COLORS.randomized} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                    <Line type="monotone" dataKey="theoretical_error" name="Error teórico" stroke={COLORS.chaining} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-2 text-xs font-semibold text-slate-200">
              Evaluación General de HyperLogLog por Día (Error vs Memoria - W2 T4)
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="py-1">Registros (m)</th>
                    <th>Memoria (bits)</th>
                    <th>Error Empírico Medio</th>
                    <th>Error Teórico (1.04/√m)</th>
                    <th>Ahorro vs Set Exacto</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-mono">
                  {hll_by_day.rows.map((row) => (
                    <tr key={row.m}>
                      <td className="py-1 text-violet-300 font-bold">{row.m}</td>
                      <td>{row.memory_bits} bits ({(row.memory_bits / 8).toFixed(0)} B)</td>
                      <td className="text-cyan-300">{pct(row.mean_rel_error)}</td>
                      <td className="text-slate-400">{pct(row.theoretical_error)}</td>
                      <td className="text-emerald-400">&gt; 99.8%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {tab === "reservoir" && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            {reservoir_view_count.map((res) => (
              <Stat
                key={res.sample_size}
                label={`Reservorio k=${res.sample_size}`}
                value={`${res.mean_error_pct_over_trials.toFixed(2)}%`}
                hint="Error medio vs Media Real (30 trials)"
                tone={res.sample_size === 500 ? "good" : "default"}
              />
            ))}
          </div>

          <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
            <h4 className="mb-2 text-xs font-semibold text-slate-200">
              Estimación de view_count_1h por Categoría según Tamaño de Muestra (W2 T3)
            </h4>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={reservoir_view_count[reservoir_view_count.length - 1].categories.map((c) => ({
                    category: c.category,
                    exact: Math.round(c.exact),
                    k100: Math.round(reservoir_view_count[0].categories.find((x) => x.category === c.category)?.estimated ?? 0),
                    k500: Math.round(c.estimated),
                  }))}
                  margin={{ top: 8, right: 8, left: -8, bottom: 16 }}
                >
                  <CartesianGrid stroke={COLORS.grid} vertical={false} />
                  <XAxis dataKey="category" {...axisProps} interval={0} fontSize={10} />
                  <YAxis {...axisProps} />
                  <Tooltip content={<ChartTooltip format={(p) => `${Number(p.value).toLocaleString()} views`} />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="exact" name="Media Exacta" fill={COLORS.randomized} isAnimationActive={false} />
                  <Bar dataKey="k100" name="Estimación k=100" fill={COLORS.chaining} isAnimationActive={false} />
                  <Bar dataKey="k500" name="Estimación k=500" fill={COLORS.twoChoices} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
