"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData } from "@/lib/types";
import { axisProps, ChartTooltip, COLORS, Panel, Segmented, Stat } from "./ui";

type Props = {
  data: DashboardData["panel_c_realtime"];
  ticks: number;
};

const pct = (v: number, d = 2) => `${(v * 100).toFixed(d)}%`;

export default function LiveMetricsPanel({ data, ticks }: Props) {
  const [scope, setScope] = useState<"all_videos" | "flagged_videos">("all_videos");
  const [bloomBits, setBloomBits] = useState<number | null>(null);

  const moments = data.frequency_moments[scope];
  const flagRates = data.flag_rate_by_category;
  const maxRate = Math.max(...flagRates.map((r) => r.flag_rate));
  const { streaming, chernoff, bloom_filter: bloom } = data;

  const bloomRow =
    bloom.configs.find((b) => b.bits_per_element === (bloomBits ?? bloom.highlight_bits_per_element)) ??
    bloom.configs[0];

  const windows = streaming.windows.map((w) => ({
    ...w,
    spamF2: w.spam_wave ? w.F2 : null, // serie aparte para pintar solo las olas
  }));
  const waves = streaming.windows.filter((w) => w.spam_wave);
  const suspicious = chernoff.summary.uploaders_suspicious;

  return (
    <Panel
      id="panel-c"
      tag="C"
      title="Métricas en vivo del stream"
      subtitle={
        <>
          {streaming.stream_events.toLocaleString()} eventos · actualización #{ticks}{" "}
          <span className="ml-1 inline-flex items-center gap-1 text-emerald-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            en vivo
          </span>
        </>
      }
      action={
        <Segmented
          value={scope}
          onChange={setScope}
          options={[
            { value: "all_videos", label: "Todos" },
            { value: "flagged_videos", label: "Marcados" },
          ]}
        />
      }
    >
      {/* Alertas */}
      <div
        id="spam-alert"
        className={`mb-3 flex items-center gap-2 rounded-xl border px-3 py-2 text-xs ${
          waves.length
            ? "border-rose-500/50 bg-rose-500/10 text-rose-200"
            : "border-emerald-400/30 bg-emerald-400/5 text-emerald-200"
        }`}
      >
        <span className={`h-2 w-2 rounded-full ${waves.length ? "animate-pulse bg-rose-400" : "bg-emerald-400"}`} />
        {waves.length ? (
          <span>
            <b>Alerta de spam:</b> {waves.length} ventana{waves.length > 1 ? "s" : ""} anómala
            {waves.length > 1 ? "s" : ""} (z &gt; 2 en F₂ o tasa de marcados) — secuencias{" "}
            {waves.map((w) => `${w.start_seq}–${w.end_seq}`).join(", ")}.
          </span>
        ) : (
          <span>Sin olas de spam detectadas en el flujo.</span>
        )}
        <span className="ml-auto whitespace-nowrap text-slate-400">
          Chernoff: {suspicious} uploader{suspicious === 1 ? "" : "s"} sospechoso
          {suspicious === 1 ? "" : "s"} (α={chernoff.summary.alpha})
        </span>
      </div>

      {/* Tarjetas */}
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat
          label="Tasa marcados"
          value={pct(data.global_flag_rate)}
          hint={`ventana reciente ${pct(streaming.recent_window_flagged_rate, 1)}`}
        />
        <Stat
          label={`F₀ (distintos)`}
          value={moments.F0}
          hint={moments.top_category ? `top: ${moments.top_category} ${pct(moments.top_share, 1)}` : undefined}
        />
        <Stat
          label="F₁ (total)"
          value={moments.F1.toLocaleString()}
          hint={`skew ×${moments.skew_ratio.toFixed(3)}`}
        />
        <Stat label="F₂ (Σ f²)" value={moments.F2.toLocaleString()} hint={`P(colisión) ${pct(moments.collision_prob, 2)}`} />
      </div>

      {/* Bloom */}
      <div className="mb-3 rounded-xl border border-white/10 bg-white/[0.03] p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
            Bloom filter · tasa de falsos positivos
          </span>
          <Segmented
            value={String(bloomRow.bits_per_element)}
            onChange={(v) => setBloomBits(Number(v))}
            options={bloom.configs.map((b) => ({
              value: String(b.bits_per_element),
              label: `${b.bits_per_element} b/el`,
            }))}
          />
        </div>
        <div className="flex items-end gap-6">
          <div>
            <div className="font-mono text-2xl font-semibold text-cyan-300">
              {pct(bloomRow.fp_rate_experimental)}
            </div>
            <div className="text-[11px] text-slate-400">experimental ({bloomRow.false_positives}/{bloomRow.negatives})</div>
          </div>
          <div>
            <div className="font-mono text-2xl font-semibold text-violet-300">
              {pct(bloomRow.fp_rate_theoretical)}
            </div>
            <div className="text-[11px] text-slate-400">teórica · k={bloomRow.hash_functions}</div>
          </div>
          <div className="ml-auto text-right text-[11px] text-slate-400">
            falsos negativos
            <div className="font-mono text-base text-emerald-300">{bloomRow.false_negatives}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {/* Tasa de marcados por categoría */}
        <div>
          <h3 className="mb-1 text-xs font-medium text-slate-300">Tasa de marcados por categoría</h3>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={flagRates} layout="vertical" margin={{ top: 4, right: 16, left: 20, bottom: 0 }}>
                <CartesianGrid stroke={COLORS.grid} horizontal={false} />
                <XAxis type="number" {...axisProps} tickFormatter={(v: number) => pct(v, 0)} domain={[0, Math.ceil(maxRate * 20) / 20]} />
                <YAxis type="category" dataKey="category" {...axisProps} width={88} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  content={<ChartTooltip format={(p) => pct(Number(p.value))} />}
                />
                <ReferenceLine x={data.global_flag_rate} stroke="#e2e8f0" strokeDasharray="4 3" />
                <Bar dataKey="flag_rate" name="Tasa" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                  {flagRates.map((r) => (
                    <Cell key={r.category} fill={r.flag_rate > data.global_flag_rate * 1.1 ? COLORS.alert : COLORS.pagerank} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[10px] text-slate-500">Línea punteada = tasa global; rojo = &gt;10 % por encima.</p>
        </div>

        {/* F2 por ventana */}
        <div>
          <h3 className="mb-1 text-xs font-medium text-slate-300">F₂ por ventana del stream</h3>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={windows} margin={{ top: 4, right: 12, left: -4, bottom: 0 }}>
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="window" {...axisProps} />
                <YAxis {...axisProps} domain={["auto", "auto"]} />
                <Tooltip
                  content={
                    <ChartTooltip
                      labelPrefix="Ventana "
                      format={(p) => Number(p.value).toLocaleString()}
                      extra={(p) => {
                        const w = windows.find((x) => x.F2 === p.value || x.spamF2 === p.value);
                        return w ? `seq ${w.start_seq}–${w.end_seq} · marcados ${pct(w.flagged_rate, 1)}` : null;
                      }}
                    />
                  }
                />
                <Line type="monotone" dataKey="F2" name="F₂" stroke={COLORS.frequency} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="spamF2" name="Ola de spam" stroke="none" dot={{ r: 5, fill: COLORS.alert, stroke: "#fff", strokeWidth: 1 }} activeDot={{ r: 6 }} isAnimationActive={false} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[10px] text-slate-500">F₂ más alto = categorías más concentradas (posible spam).</p>
        </div>
      </div>
    </Panel>
  );
}
