"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardData } from "@/lib/types";
import { axisProps, ChartTooltip, COLORS, Panel, Stat } from "./ui";

type Props = { data: DashboardData["panel_a_bucket_load"] };

export default function BucketDistributionChart({ data }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const key = selected && data.configs[selected] ? selected : data.default_config;
  const cfg = data.configs[key];

  const options = useMemo(
    () =>
      Object.entries(data.configs)
        .sort(([, a], [, b]) => a.n - b.n || a.buckets - b.buckets)
        .map(([k, c]) => ({ k, label: `n=${c.n.toLocaleString()} · m=${c.buckets}` })),
    [data.configs],
  );

  // Recorta las columnas vacías de los extremos para que las barras sean legibles.
  const rows = useMemo(() => {
    const h = cfg.histogram;
    const used = h.filter((r) => r.chaining > 0 || r.two_choices > 0);
    if (!used.length) return h;
    const lo = used[0].load;
    const hi = used[used.length - 1].load;
    return h.filter((r) => r.load >= lo && r.load <= hi);
  }, [cfg]);

  const c = cfg.stats.chaining;
  const t = cfg.stats.two_choices;

  return (
    <Panel
      id="panel-a"
      tag="A"
      title="Distribución de carga por bucket"
      subtitle="Nº de buckets (eje Y) con una carga dada (eje X). Two Choices concentra la masa cerca de la media; Chaining tiene cola larga."
      action={
        <select
          id="bucket-config-select"
          aria-label="Configuración de hashing"
          value={key}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-lg border border-white/10 bg-slate-950/70 px-2 py-1 text-xs text-slate-200 outline-none focus:border-violet-400"
        >
          {options.map((o) => (
            <option key={o.k} value={o.k}>
              {o.label}
            </option>
          ))}
        </select>
      }
    >
      <div className="mb-3 grid grid-cols-2 gap-2">
        <Stat
          label="Carga máx · Chaining"
          value={c?.max_load ?? "—"}
          hint={c ? `σ = ${c.std.toFixed(2)}` : undefined}
          tone="alert"
        />
        <Stat
          label="Carga máx · Two Choices"
          value={t?.max_load ?? "—"}
          hint={t ? `σ = ${t.std.toFixed(2)}` : undefined}
          tone="good"
        />
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: -12, bottom: 16 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis
              dataKey="load"
              {...axisProps}
              label={{ value: "Carga del bucket", position: "insideBottom", offset: -8, fill: COLORS.axis, fontSize: 11 }}
            />
            <YAxis {...axisProps} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.05)" }}
              content={
                <ChartTooltip labelPrefix="Carga " format={(p) => `${p.value} buckets`} />
              }
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 4 }} />
            <Bar dataKey="chaining" name="Chaining" fill={COLORS.chaining} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="two_choices" name="Power of Two Choices" fill={COLORS.twoChoices} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
