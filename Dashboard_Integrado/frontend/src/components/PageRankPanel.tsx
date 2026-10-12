"use client";

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
    <div className="max-w-56 rounded-lg border border-white/15 bg-slate-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 font-semibold text-slate-100">{row.category}</div>
      <div className="text-violet-300">
        PageRank: <span className="font-mono">{row.pagerank_scaled.toFixed(1)}</span>/100 · raw{" "}
        <span className="font-mono">{row.pagerank.toFixed(4)}</span> · rango #{row.pagerank_rank}
      </div>
      <div className="mt-0.5 text-sky-300">
        Frecuencia: <span className="font-mono">{row.frequency_scaled.toFixed(1)}</span>/100 ·{" "}
        {row.upload_count.toLocaleString()} subidas · rango #{row.frequency_rank}
      </div>
      <div className="mt-1.5 border-t border-white/10 pt-1.5 text-[10px] leading-snug text-slate-400">
        Escala min–max por métrica: las categorías son casi uniformes, así que las diferencias
        reales son mínimas.
      </div>
    </div>
  );
}

export default function PageRankPanel({ data }: Props) {
  const rows = data.categories;
  const rho = data.meta.spearman_rank_correlation;
  const biggest = [...rows].sort((a, b) => Math.abs(b.rank_delta) - Math.abs(a.rank_delta))[0];
  const rawSpreadPct = data.meta.pagerank_spread * 100;

  return (
    <Panel
      id="panel-d"
      tag="D"
      title="PageRank vs. frecuencia de subidas"
      subtitle={
        <>
          Valores reescalados a 0–100 (min–max) para hacer visibles las diferencias.{" "}
          <span
            title="Las probabilidades de transición entre categorías son casi uniformes: el rango bruto de PageRank es de solo ~0.7 puntos porcentuales, y las frecuencias de subida difieren en pocas decenas de videos. Interpreta las diferencias como ruido leve, no como jerarquías marcadas."
            className="cursor-help rounded border border-amber-400/40 bg-amber-400/10 px-1.5 py-0.5 text-amber-200"
          >
            ⓘ categorías casi uniformes
          </span>
        </>
      }
    >
      <div className="mb-3 grid grid-cols-3 gap-2">
        <Stat
          label="Correlación de rangos"
          value={rho === null ? "—" : rho.toFixed(2)}
          hint="PR vs frecuencia"
        />
        <Stat
          label="Rango bruto PR"
          value={`${rawSpreadPct.toFixed(2)} pp`}
          hint={`d=${data.meta.damping} · ${data.meta.iterations} iter`}
          tone="alert"
        />
        <Stat
          label="Mayor salto"
          value={`${biggest.rank_delta > 0 ? "+" : ""}${biggest.rank_delta}`}
          hint={biggest.category}
        />
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={rows} outerRadius="72%">
            <PolarGrid stroke={COLORS.grid} />
            <PolarAngleAxis dataKey="category" tick={{ fill: "#cbd5e1", fontSize: 10 }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: COLORS.axis, fontSize: 9 }} tickCount={5} stroke={COLORS.grid} />
            <Tooltip content={<RadarTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Radar name="PageRank (0–100)" dataKey="pagerank_scaled" stroke={COLORS.pagerank} fill={COLORS.pagerank} fillOpacity={0.3} strokeWidth={2} isAnimationActive={false} />
            <Radar name="Frecuencia de subidas (0–100)" dataKey="frequency_scaled" stroke={COLORS.frequency} fill={COLORS.frequency} fillOpacity={0.2} strokeWidth={2} isAnimationActive={false} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
