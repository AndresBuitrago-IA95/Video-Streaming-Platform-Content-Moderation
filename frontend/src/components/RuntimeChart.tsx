"use client";

import { useState } from "react";
import {
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
import { axisProps, ChartTooltip, COLORS, Panel, Segmented, Stat } from "./ui";

type Props = { data: DashboardData["panel_b_runtimes"] };

const LABELS: Record<string, string> = {
  ordenado: "Ordenado",
  inverso: "Inverso",
  original: "Aleatorio",
};

export default function RuntimeChart({ data }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [log, setLog] = useState(false);

  const scenario =
    selected && data.scenarios[selected] ? selected : data.default_scenario;
  const rows = data.scenarios[scenario];
  const last = rows[rows.length - 1];
  const ratio = last.deterministic_ms / last.randomized_ms;

  const scenarioOptions = Object.keys(data.scenarios).map((s) => ({
    value: s,
    label: LABELS[s] ?? s,
  }));

  return (
    <Panel
      id="panel-b"
      tag="B"
      title="QuickSort: aleatorizado vs. determinista"
      subtitle="Tiempo promedio (ms) por tamaño de entrada. El pivote fijo degenera a O(n²) en entradas ya ordenadas; el aleatorio mantiene O(n log n) esperado."
      action={
        <div className="flex flex-col items-end gap-1.5">
          <Segmented value={scenario} options={scenarioOptions} onChange={setSelected} />
          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-slate-400">
            <input
              id="runtime-log-toggle"
              type="checkbox"
              checked={log}
              onChange={(e) => setLog(e.target.checked)}
              className="accent-violet-500"
            />
            Escala log
          </label>
        </div>
      }
    >
      <div className="mb-3 grid grid-cols-2 gap-2">
        <Stat
          label={`Det. n=${last.n.toLocaleString()}`}
          value={`${last.deterministic_ms.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms`}
          tone={ratio > 5 ? "alert" : "default"}
        />
        <Stat
          label={`Aleat. n=${last.n.toLocaleString()}`}
          value={`${last.randomized_ms.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms`}
          hint={ratio > 1.2 ? `${ratio.toFixed(0)}× más rápido` : "tiempos comparables"}
          tone="good"
        />
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, left: -4, bottom: 16 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis
              dataKey="n"
              {...axisProps}
              tickFormatter={(v: number) => v.toLocaleString()}
              label={{ value: "Tamaño de entrada n", position: "insideBottom", offset: -8, fill: COLORS.axis, fontSize: 11 }}
            />
            <YAxis
              {...axisProps}
              scale={log ? "log" : "linear"}
              domain={log ? [0.5, "auto"] : [0, "auto"]}
              allowDataOverflow={log}
              tickFormatter={(v: number) => (v >= 1000 ? `${v / 1000}k` : String(v))}
              unit=" ms"
            />
            <Tooltip
              content={
                <ChartTooltip
                  labelPrefix="n = "
                  format={(p) => `${Number(p.value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ms`}
                />
              }
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 4 }} />
            <Line type="monotone" dataKey="deterministic_ms" name="Determinista" stroke={COLORS.deterministic} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
            <Line type="monotone" dataKey="randomized_ms" name="Aleatorizado" stroke={COLORS.randomized} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
