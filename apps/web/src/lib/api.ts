"use client";

/**
 * Typed client for the ERDA data plane (proxied via /api/erda → FastAPI).
 * Every quantitative payload carries provenance; components render numbers
 * ONLY from these shapes — a number without provenance is a bug (§0 rule 5).
 */

import { useEffect, useRef, useState } from "react";

export interface Provenance {
  source_id: string;
  retrieved_at: string;
  source_url: string;
  transform_version: string;
}

export interface TickerInstrument {
  label: string;
  value: number;
  unit: string;
  delta?: number | null;
  note?: string;
  asof: string;
  indicative?: boolean;
  provenance: Provenance;
}

export interface StripContract {
  month_index: number;
  contract: string;
  expiry: string;
  settle_usd_bbl: number;
}

export interface CurvePayload {
  available: boolean;
  strip?: {
    asof: string;
    indicative: boolean;
    contracts: StripContract[];
    prompt_spread: number;
    slope_m1_m12: number;
    structure: string;
    provenance: Provenance;
  };
  spot_history?: Record<string, { date: string; value: number }[]>;
  spot_provenance?: Provenance;
}

export interface InventorySeries {
  asof: string;
  latest_kbbl: number;
  wow_change_kbbl: number | null;
  weekly: { week: string; value_kbbl: number }[];
  five_year_band: { week_of_year: number; band_min: number; band_max: number }[];
}

export interface InventoriesPayload {
  available: boolean;
  reason?: string;
  provenance?: Provenance;
  series?: Record<string, InventorySeries>;
  days_of_cover?: number;
}

export interface OpecRow {
  country: string;
  production_kbd: number;
  target_kbd: number | null;
  pct_of_target: number | null;
  notes: string;
  target_source_url: string | null;
}

export interface OpecPayload {
  available: boolean;
  reason?: string;
  month?: string;
  extraction?: string;
  rows?: OpecRow[];
  production_provenance?: Provenance;
  targets_provenance?: Provenance;
}

export interface SourceStatus {
  source_id: string;
  name: string;
  cadence: string;
  sla_days: number;
  verified_at: string;
  freshness: {
    age_days: number | null;
    sla_days: number;
    retrieved_at: string | null;
    status: "pass" | "warn" | "fail";
    detail: string;
  } | null;
}

export interface ValidationReport {
  generated_at: string;
  transform_version: string;
  summary: { pass: number; warn: number; fail: number; overall: string };
  sections: Record<string, Record<string, unknown>[]>;
}

/** Poll an ERDA endpoint. Terminal cadence: default 60 s, no jitter theatrics. */
export function useErda<T>(path: string, refreshMs = 60_000): {
  data: T | null;
  error: string | null;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const resp = await fetch(`/api/erda/${path}`);
        if (!resp.ok) throw new Error(`${resp.status}`);
        const body = (await resp.json()) as T;
        if (alive) {
          setData(body);
          setError(null);
        }
      } catch (err) {
        if (alive) setError(err instanceof Error ? err.message : "fetch failed");
      }
    };
    void load();
    timer.current = setInterval(load, refreshMs);
    return () => {
      alive = false;
      if (timer.current) clearInterval(timer.current);
    };
  }, [path, refreshMs]);

  return { data, error };
}
