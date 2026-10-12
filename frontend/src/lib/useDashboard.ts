"use client";

import { useEffect, useState } from "react";
import type { DashboardData } from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/dashboard";

export interface DashboardState {
  data: DashboardData | null;
  error: string | null;
  lastUpdated: Date | null;
  /** nº de peticiones exitosas desde que se montó la página */
  ticks: number;
}

/**
 * Consulta periódicamente la API para simular un entorno de streaming en tiempo real.
 * Si una petición falla se conserva el último dato válido y se expone `error`.
 */
export function useDashboard(intervalMs = 5000): DashboardState {
  const [state, setState] = useState<DashboardState>({
    data: null,
    error: null,
    lastUpdated: null,
    ticks: 0,
  });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const res = await fetch(API_URL, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as DashboardData;
        setState((s) => ({
          data,
          error: null,
          lastUpdated: new Date(),
          ticks: s.ticks + 1,
        }));
      } catch (e) {
        if (controller.signal.aborted) return;
        setState((s) => ({
          ...s,
          error: e instanceof Error ? e.message : "Error desconocido",
        }));
      }
    }

    load();
    const id = setInterval(load, intervalMs);
    return () => {
      controller.abort();
      clearInterval(id);
    };
  }, [intervalMs]);

  return state;
}
