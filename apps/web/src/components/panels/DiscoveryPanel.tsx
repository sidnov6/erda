"use client";

import {
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type Provenance, useErda } from "@/lib/api";

interface DiscoveryPayload {
  available: boolean;
  reason?: string;
  provenance?: Provenance;
  n_primary?: number;
  success_rate?: number;
  boem_proxy_note?: string;
  per_year?: { spud_year: number; wildcats: number; discoveries: number; success_rate: number }[];
}

/**
 * DISC (§8.7): exploration wells/year (bars, right scale) vs success rate
 * (line, left scale 0–100%) from the harmonized label DB. Volumes stay absent
 * until the gated GOGET XLSX exists — count-based, honestly labelled.
 */
function DiscoveryChart({ perYear }: { perYear: NonNullable<DiscoveryPayload["per_year"]> }) {
  const holder = useRef<HTMLDivElement | null>(null);
  const chart = useRef<IChartApi | null>(null);
  const bars = useRef<ISeriesApi<"Histogram"> | null>(null);
  const rate = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    const el = holder.current;
    if (!el) return;
    const c = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#A89E8F",
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: { vertLines: { color: "#262019" }, horzLines: { color: "#262019" } },
      rightPriceScale: { borderColor: "#262019" },
      leftPriceScale: { visible: true, borderColor: "#262019" },
      timeScale: { borderColor: "#262019" },
      crosshair: {
        vertLine: { color: "#6E6558", labelBackgroundColor: "#14110C" },
        horzLine: { color: "#6E6558", labelBackgroundColor: "#14110C" },
      },
      handleScroll: false,
      handleScale: false,
    });
    bars.current = c.addSeries(HistogramSeries, {
      color: "rgba(95, 179, 201, 0.5)", // --cyan dim — counts, not deltas
      priceScaleId: "right",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    rate.current = c.addSeries(LineSeries, {
      color: "#3FA66A", // --oil — the discovery-rate line
      lineWidth: 1,
      priceScaleId: "left",
      priceLineVisible: false,
      lastValueVisible: false,
      priceFormat: { type: "custom", formatter: (v: number) => `${Math.round(v)}%`, minMove: 1 },
    });
    chart.current = c;
    return () => {
      c.remove();
      chart.current = null;
      bars.current = null;
      rate.current = null;
    };
  }, []);

  useEffect(() => {
    if (!bars.current || !rate.current) return;
    const time = (y: number) => `${y}-01-01`;
    bars.current.setData(perYear.map((r) => ({ time: time(r.spud_year), value: r.wildcats })));
    rate.current.setData(
      perYear.map((r) => ({ time: time(r.spud_year), value: r.success_rate * 100 }))
    );
    chart.current?.timeScale().fitContent();
  }, [perYear]);

  return <div ref={holder} className="h-full w-full" />;
}

export function DiscoveryPanel() {
  const { data } = useErda<DiscoveryPayload>("panels/discovery", 300_000);

  if (!data || !data.available || !data.per_year) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote={data?.reason ?? "LABEL DB · 5 REGULATORS — P2"} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        <span className="chip gap-1">
          WILDCATS <span className="numeric text-ink">{data.n_primary?.toLocaleString()}</span>
        </span>
        <span className="chip gap-1" title={data.boem_proxy_note}>
          SUCCESS{" "}
          <span className="numeric text-ink">
            {data.success_rate != null ? (data.success_rate * 100).toFixed(1) : "—"}%
          </span>
        </span>
        <span className="flex-1" />
        {data.provenance && <ProvenanceChip prov={data.provenance} label="LABELS" />}
      </div>
      <div className="min-h-0 flex-1 px-2 pb-1">
        <DiscoveryChart perYear={data.per_year} />
      </div>
    </div>
  );
}
