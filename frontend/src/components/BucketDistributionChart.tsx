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
  const [tab, setTab] = useState<"buckets" | "sharding">("buckets");
  const key = selected && data.configs[selected] ? selected : data.default_config;
  const cfg = data.configs[key];

  const options = useMemo(
    () =>
      Object.entries(data.configs)
        .sort(([, a], [, b]) => a.n - b.n || a.buckets - b.buckets)
        .map(([k, c]) => ({ k, label: `n=${c.n.toLocaleString()} pendientes · m=${c.buckets}` })),
    [data.configs],
  );

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
  const sharding = data.sharding;

  return (
    <Panel
      id="panel-a"
      tag="A"
      title="Hashing y Colas de Moderación (W1)"
      subtitle={
        tab === "buckets"
          ? `Tabla hash por categoría de videos pendientes (clave: ${data.key}). Chaining vs Two Choices.`
          : `Sharding de moderación (W1 T3): distribución de uploader_id entre ${sharding.workers} revisores.`
      }
      action={
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
            <button
              onClick={() => setTab("buckets")}
              className={`rounded px-2 py-0.5 text-xs ${
                tab === "buckets" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Tabla Hash (T4)
            </button>
            <button
              onClick={() => setTab("sharding")}
              className={`rounded px-2 py-0.5 text-xs ${
                tab === "sharding" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Sharding Revisores (T3)
            </button>
          </div>
          {tab === "buckets" && (
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
          )}
        </div>
      }
    >
      {tab === "buckets" ? (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat
              label="Carga máx · Chaining"
              value={c?.max_load ?? "—"}
              hint={c ? `Teórica: ~${c.theoretical_max?.toFixed(1)}` : undefined}
              tone="alert"
            />
            <Stat
              label="Carga máx · Two Choices"
              value={t?.max_load ?? "—"}
              hint={t ? `Teórica: ~${t.theoretical_max?.toFixed(1)}` : undefined}
              tone="good"
            />
            <Stat
              label="Desv. Estándar σ"
              value={`${t?.std.toFixed(2)} vs ${c?.std.toFixed(2)}`}
              hint="Two Choices vs Chaining"
            />
            <Stat
              label="Buckets Vacíos"
              value={`${t?.empty_buckets} vs ${c?.empty_buckets}`}
              hint="Two Choices vs Chaining"
            />
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 8, right: 8, left: -12, bottom: 16 }}>
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis
                  dataKey="load"
                  {...axisProps}
                  label={{ value: "Carga del bucket (videos asignados)", position: "insideBottom", offset: -8, fill: COLORS.axis, fontSize: 11 }}
                />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  content={
                    <ChartTooltip labelPrefix="Carga " format={(p) => `${p.value} buckets`} />
                  }
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 4 }} />
                <Bar dataKey="chaining" name="Chaining (h1)" fill={COLORS.chaining} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="two_choices" name="Power of Two Choices" fill={COLORS.twoChoices} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Revisores (Workers)" value={sharding.workers} hint="Sharding universal" />
            <Stat label="Colisiones Asignación" value={sharding.collisions.toLocaleString()} hint={`${sharding.distinct_uploaders} uploaders`} tone="alert" />
            <Stat label="Carga Media / Worker" value={`${sharding.mean_videos.toFixed(1)}`} hint={`Min: ${sharding.min_videos} | Max: ${sharding.max_videos}`} />
            <Stat label="Ratio Desbalance" value={`×${sharding.imbalance_ratio.toFixed(2)}`} hint={`σ = ${sharding.std_videos.toFixed(1)}`} tone="good" />
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={sharding.videos_per_worker.map((v, i) => ({ worker: `W${i}`, videos: v }))}
                margin={{ top: 8, right: 8, left: -12, bottom: 16 }}
              >
                <CartesianGrid stroke={COLORS.grid} vertical={false} />
                <XAxis dataKey="worker" {...axisProps} interval={1} />
                <YAxis {...axisProps} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  content={<ChartTooltip labelPrefix="Trabajador " format={(p) => `${p.value} videos`} />}
                />
                <Bar dataKey="videos" name="Videos Asignados" fill={COLORS.frequency} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Panel>
  );
}
