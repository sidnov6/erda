"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
} from "lightweight-charts";
import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type CurvePayload, type StripContract, useErda } from "@/lib/api";

/* Canvas text/strokes cannot resolve CSS variables, so the skill §4a reference
   config uses hex literals that mirror §1 tokens exactly. Reference, never adjust. */
const INK_DIM = "#A89E8F"; // --ink-dim
const LINE = "#262019"; //   --line
const DRY = "#6E6558"; //    --dry
const BG1 = "#14110C"; //    --bg1
const GOLD = "#E8A33D"; //   --gold — the strip line is THE gold element (curve M1)
const CYAN = "#5FB3C9"; //   --cyan — brent, secondary series

const SPOT_WINDOW = 260; // ~1y of trading days from the 520-point history

/** next/font hashes family names; resolve the real one for the chart canvas. */
function monoFamily(el: HTMLElement): string {
  const v = getComputedStyle(el).getPropertyValue("--font-plex-mono").trim();
  return v !== "" ? v : "'IBM Plex Mono', monospace";
}

/** Skill §4a chart theme. Fixed windows (12M strip / 1y spot): pan-zoom would
    carry no information, so scroll/scale are off; crosshair inspection stays. */
function chartOptions(el: HTMLElement) {
  return {
    width: el.clientWidth,
    height: el.clientHeight,
    layout: {
      background: { type: ColorType.Solid, color: "transparent" }, // panel supplies --bg1
      textColor: INK_DIM,
      fontFamily: monoFamily(el),
      fontSize: 11,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: LINE },
      horzLines: { color: LINE },
    },
    rightPriceScale: { borderColor: LINE },
    timeScale: { borderColor: LINE, fixLeftEdge: true, fixRightEdge: true },
    crosshair: {
      vertLine: { color: DRY, labelBackgroundColor: BG1 },
      horzLine: { color: DRY, labelBackgroundColor: BG1 },
    },
    handleScroll: false,
    handleScale: false,
  };
}

/** Ascending, deduped by date — lightweight-charts throws on unordered input. */
function toLineData(points: { date: string; value: number }[]): LineData<Time>[] {
  const sorted = [...points].sort((a, b) =>
    a.date < b.date ? -1 : a.date > b.date ? 1 : 0
  );
  const out: LineData<Time>[] = [];
  for (const p of sorted) {
    const last = out[out.length - 1];
    if (last && last.time === p.date) last.value = p.value;
    else out.push({ time: p.date, value: p.value });
  }
  return out;
}

/** Create a chart in the returned container, resize with the panel via
    ResizeObserver → applyOptions({width,height}), dispose cleanly on unmount. */
function useTerminalChart(init: (chart: IChartApi) => void) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const initRef = useRef(init);
  initRef.current = init;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, chartOptions(el));
    initRef.current(chart);
    const ro = new ResizeObserver((entries) => {
      const rect = entries[entries.length - 1]?.contentRect;
      if (rect && rect.width > 0 && rect.height > 0) {
        chart.applyOptions({
          width: Math.floor(rect.width),
          height: Math.floor(rect.height),
        });
      }
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, []);

  return containerRef;
}

/** The strip: settle vs. contract expiry, one gold line, no fill — the chip row
    states structure, so no contango/backwardation shading competes with it. */
function StripChart({ contracts }: { contracts: StripContract[] }) {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const containerRef = useTerminalChart((chart) => {
    chartRef.current = chart;
    seriesRef.current = chart.addSeries(LineSeries, {
      color: GOLD,
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
  });

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const points = [...contracts]
      .sort((a, b) => a.month_index - b.month_index)
      .map((c) => ({ date: c.expiry, value: c.settle_usd_bbl }));
    series.setData(toLineData(points));
    chartRef.current?.timeScale().fitContent();
  }, [contracts]);

  return <div ref={containerRef} className="h-full w-full" />;
}

/** Spot history, last ~1y: brent --cyan, wti --dry (secondary series, §4a). */
function SpotChart({
  brent,
  wti,
}: {
  brent: { date: string; value: number }[];
  wti: { date: string; value: number }[];
}) {
  const chartRef = useRef<IChartApi | null>(null);
  const brentRef = useRef<ISeriesApi<"Line"> | null>(null);
  const wtiRef = useRef<ISeriesApi<"Line"> | null>(null);
  const containerRef = useTerminalChart((chart) => {
    chartRef.current = chart;
    const opts = { lineWidth: 1, lastValueVisible: false, priceLineVisible: false } as const;
    brentRef.current = chart.addSeries(LineSeries, { ...opts, color: CYAN });
    wtiRef.current = chart.addSeries(LineSeries, { ...opts, color: DRY });
  });

  useEffect(() => {
    if (!brentRef.current || !wtiRef.current) return;
    brentRef.current.setData(toLineData(brent));
    wtiRef.current.setData(toLineData(wti));
    chartRef.current?.timeScale().fitContent();
  }, [brent, wti]);

  return <div ref={containerRef} className="h-full w-full" />;
}

function fmtSigned(v: number): string {
  return v >= 0 ? `+${v.toFixed(2)}` : v.toFixed(2);
}

/** CRV — price & curve deck (spec §8.2): strip line over spot history. */
export function CurvePanel() {
  const { data } = useErda<CurvePayload>("panels/curve");

  if (!data || !data.available) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote="FRED · YF_CURVE — P1" />
      </div>
    );
  }

  const strip =
    data.strip && data.strip.contracts.length > 0 ? data.strip : undefined;
  const m1 = strip
    ? [...strip.contracts].sort((a, b) => a.month_index - b.month_index)[0]
    : undefined;
  const brent = (data.spot_history?.["brent"] ?? []).slice(-SPOT_WINDOW);
  const wti = (data.spot_history?.["wti"] ?? []).slice(-SPOT_WINDOW);
  const hasSpot = brent.length > 0 || wti.length > 0;
  const brentLast = brent[brent.length - 1];
  const wtiLast = wti[wti.length - 1];

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        {strip && (
          <>
            {/* Structure is a stated fact, not an alert — ink-dim per convention. */}
            <span
              className="chip"
              title={`asof ${strip.asof}${strip.indicative ? " · indicative" : ""}`}
            >
              {strip.structure.toUpperCase()}
            </span>
            {m1 && (
              <span className="chip" title={`M1 ${m1.contract} · expiry ${m1.expiry}`}>
                {m1.contract.split(".")[0]}&nbsp;
                <span className="numeric text-gold">
                  {m1.settle_usd_bbl.toFixed(2)}
                </span>
              </span>
            )}
            <span className="chip">
              M1–M2&nbsp;
              <span className="numeric text-ink">{fmtSigned(strip.prompt_spread)}</span>
            </span>
            <span className="chip">
              M1–M12&nbsp;
              <span className="numeric text-ink">{fmtSigned(strip.slope_m1_m12)}</span>
            </span>
            <ProvenanceChip
              prov={strip.provenance}
              label={strip.indicative ? "~YF" : "YF"}
            />
          </>
        )}
        {data.spot_provenance && <ProvenanceChip prov={data.spot_provenance} />}
      </div>

      {strip && (
        <>
          <div className="flex items-baseline justify-between px-2 text-[11px] text-ink-faint">
            <span className="font-mono">STRIP · M1–M12 · USD/BBL</span>
            <span className="numeric">ASOF {strip.asof}</span>
          </div>
          <div className="min-h-0 flex-[3] px-2 pb-1">
            <StripChart contracts={strip.contracts} />
          </div>
        </>
      )}

      {hasSpot && (
        <>
          <div className="flex items-baseline gap-3 px-2 text-[11px]">
            <span className="font-mono text-ink-faint">SPOT · 1Y · USD/BBL</span>
            {brentLast && (
              <span className="font-mono text-cyan" title={`asof ${brentLast.date}`}>
                BRENT&nbsp;
                <span className="numeric">{brentLast.value.toFixed(2)}</span>
              </span>
            )}
            {wtiLast && (
              <span className="font-mono text-dry" title={`asof ${wtiLast.date}`}>
                WTI&nbsp;
                <span className="numeric">{wtiLast.value.toFixed(2)}</span>
              </span>
            )}
          </div>
          <div className="min-h-0 flex-[2] px-2 pb-1">
            <SpotChart brent={brent} wti={wti} />
          </div>
        </>
      )}

      {!strip && !hasSpot && (
        <EmptyState feedNote="FRED · YF_CURVE — payload empty" />
      )}
    </div>
  );
}
