import type { ReactNode } from "react";

export const COLORS = {
  chaining: "#fb7185",
  twoChoices: "#22d3ee",
  deterministic: "#f59e0b",
  randomized: "#34d399",
  pagerank: "#a78bfa",
  frequency: "#38bdf8",
  alert: "#f43f5e",
  grid: "rgba(148,163,184,0.15)",
  axis: "#94a3b8",
} as const;

export const axisProps = {
  stroke: COLORS.axis,
  tick: { fill: COLORS.axis, fontSize: 11 },
  tickLine: false,
} as const;

export function Panel({
  id,
  tag,
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  id: string;
  tag: string;
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-xl shadow-black/30 backdrop-blur-xl transition hover:border-violet-400/30 ${className}`}
    >
      <div className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-violet-500/10 blur-3xl transition group-hover:bg-cyan-400/10" />
      <header className="relative mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded-md bg-gradient-to-br from-violet-500 to-cyan-400 text-xs font-bold text-slate-950">
              {tag}
            </span>
            <h2 className="text-base font-semibold text-slate-100">{title}</h2>
          </div>
          {subtitle && (
            <p className="mt-1 text-xs leading-relaxed text-slate-400">{subtitle}</p>
          )}
        </div>
        {action}
      </header>
      <div className="relative flex-1">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "good" | "alert";
}) {
  const ring =
    tone === "alert"
      ? "border-rose-500/40 bg-rose-500/10"
      : tone === "good"
        ? "border-emerald-400/30 bg-emerald-400/5"
        : "border-white/10 bg-white/[0.03]";
  return (
    <div className={`rounded-xl border px-3 py-2.5 ${ring}`}>
      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="mt-0.5 font-mono text-xl font-semibold text-slate-50">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-slate-400">{hint}</div>}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-white/10 bg-slate-950/60 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
            value === o.value
              ? "bg-violet-500/80 text-white shadow"
              : "text-slate-400 hover:text-slate-100"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

interface TipItem {
  name?: string | number;
  value?: string | number | readonly (string | number)[];
  color?: string;
  dataKey?: string | number;
}

/** Tooltip oscuro reutilizable; `format` personaliza el valor de cada serie. */
export function ChartTooltip({
  active,
  payload,
  label,
  labelPrefix = "",
  format,
  extra,
}: {
  active?: boolean;
  payload?: readonly TipItem[];
  label?: string | number;
  labelPrefix?: string;
  format?: (item: TipItem) => string;
  extra?: (item: TipItem) => ReactNode;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-white/15 bg-slate-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 font-semibold text-slate-100">
        {labelPrefix}
        {label}
      </div>
      {payload.map((p, i) => (
        <div key={`${p.dataKey}-${i}`} className="flex items-center gap-2 text-slate-300">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span>{p.name}:</span>
          <span className="font-mono text-slate-50">
            {format ? format(p) : String(p.value)}
          </span>
        </div>
      ))}
      {extra && payload[0] && <div className="mt-1 text-slate-400">{extra(payload[0])}</div>}
    </div>
  );
}
