"use client";

import {
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type InventoriesPayload, type InventorySeries, useErda } from "@/lib/api";

/** INV — weekly stocks as bars vs the 5-yr range band (spec §8.4). */

const SERIES_TABS = [
  { key: "crude_stocks_excl_spr_kbbl", label: "CRUDE" },
  { key: "gasoline_stocks_kbbl", label: "GASO" },
  { key: "distillate_stocks_kbbl", label: "DIST" },
] as const;

type SeriesKey = (typeof SERIES_TABS)[number]["key"];

const fmtKbbl = (v: number) => Math.round(v).toLocaleString("en-US");

/**
 * ISO-8601 week number. Must match the API's five_year_band keying, which is
 * pandas `DatetimeIndex.isocalendar().week` (packages/ingestion derived.py).
 */
function isoWeek(dateStr: string): number {
  const d = new Date(
    Date.UTC(
      Number(dateStr.slice(0, 4)),
      Number(dateStr.slice(5, 7)) - 1,
      Number(dateStr.slice(8, 10))
    )
  );
  const dayNum = (d.getUTCDay() + 6) % 7; // Mon=0 … Sun=6
  d.setUTCDate(d.getUTCDate() - dayNum + 3); // Thursday of this ISO week
  const firstThursday = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const firstDayNum = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstDayNum + 3);
  return 1 + Math.round((d.getTime() - firstThursday.getTime()) / 604_800_000);
}

/**
 * Weekly bars (--cyan, dimmed — levels, not deltas, so never red/green) with
 * the 5-yr min/max as thin dashed --dry lines. Band values are mapped onto the
 * displayed window's week dates via ISO week-of-year; weeks with no band entry
 * are simply skipped — never interpolated.
 */
function StocksChart({ series }: { series: InventorySeries }) {
  const holder = useRef<HTMLDivElement | null>(null);
  const chart = useRef<IChartApi | null>(null);
  const bars = useRef<ISeriesApi<"Histogram"> | null>(null);
  const bandLo = useRef<ISeriesApi<"Line"> | null>(null);
  const bandHi = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    const el = holder.current;
    if (!el) return;
    // Skill §4a config — tokens as literals because lightweight-charts wants
    // resolved colors, not CSS vars.
    const c = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" }, // panel supplies --bg1
        textColor: "#A89E8F", // --ink-dim
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#262019" }, // --line
        horzLines: { color: "#262019" },
      },
      rightPriceScale: { borderColor: "#262019" },
      timeScale: { borderColor: "#262019" },
      crosshair: {
        vertLine: { color: "#6E6558", labelBackgroundColor: "#14110C" }, // --dry / --bg1
        horzLine: { color: "#6E6558", labelBackgroundColor: "#14110C" },
      },
      localization: { priceFormatter: fmtKbbl },
    });
    const bandOpts = {
      color: "#6E6558", // --dry
      lineWidth: 1 as const,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      priceFormat: { type: "custom" as const, formatter: fmtKbbl, minMove: 1 },
    };
    bandLo.current = c.addSeries(LineSeries, bandOpts);
    bandHi.current = c.addSeries(LineSeries, bandOpts);
    bars.current = c.addSeries(HistogramSeries, {
      color: "rgba(95, 179, 201, 0.5)", // --cyan, dimmed
      priceLineVisible: false,
      // The chip row already states the latest level; the on-axis tag only
      // collides with scale labels at panel height.
      lastValueVisible: false,
      priceFormat: { type: "custom", formatter: fmtKbbl, minMove: 1 },
    });
    chart.current = c;
    return () => {
      c.remove();
      chart.current = null;
      bars.current = null;
      bandLo.current = null;
      bandHi.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chart.current || !bars.current || !bandLo.current || !bandHi.current) return;
    const weekly = [...series.weekly].sort((a, b) => (a.week < b.week ? -1 : 1));
    const bandByWeek = new Map(series.five_year_band.map((b) => [b.week_of_year, b]));
    const lo: { time: string; value: number }[] = [];
    const hi: { time: string; value: number }[] = [];
    for (const p of weekly) {
      const band = bandByWeek.get(isoWeek(p.week));
      if (band) {
        lo.push({ time: p.week, value: band.band_min });
        hi.push({ time: p.week, value: band.band_max });
      }
    }
    // Bars are absolute levels ~400 Mbbl; a zero base would crush the signal.
    // Anchor the histogram base just below the window's min (positioning only —
    // every rendered value is straight from the payload).
    const values = [
      ...weekly.map((p) => p.value_kbbl),
      ...lo.map((p) => p.value),
      ...hi.map((p) => p.value),
    ];
    if (values.length === 0) return;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || Math.abs(max) * 0.01 || 1;
    bars.current.applyOptions({ base: Math.max(0, min - span * 0.06) });
    bars.current.setData(weekly.map((p) => ({ time: p.week, value: p.value_kbbl })));
    bandLo.current.setData(lo);
    bandHi.current.setData(hi);
    chart.current.timeScale().fitContent();
  }, [series]);

  return <div ref={holder} className="h-full w-full" />;
}

/** INV — Inventories: cover/WoW chip row, series selector, bars vs 5-yr band. */
export function InventoriesPanel() {
  const { data } = useErda<InventoriesPayload>("panels/inventories");
  const [selKey, setSelKey] = useState<SeriesKey>(SERIES_TABS[0].key);

  if (!data || !data.available || !data.series) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote={data?.reason ?? "EIA WPSR · JODI — P1"} />
      </div>
    );
  }

  const sel = data.series[selKey];
  const wow = sel?.wow_change_kbbl ?? null;
  const wowCls = wow == null || wow === 0 ? "text-ink-dim" : wow > 0 ? "text-oil" : "text-gas";
  const wowText =
    wow == null
      ? null
      : `${wow > 0 ? "▲ +" : wow < 0 ? "▼ −" : ""}${fmtKbbl(Math.abs(wow))} kbbl`;

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        {data.days_of_cover != null && (
          <span className="chip gap-1">
            COVER{" "}
            <span className="numeric text-ink">{data.days_of_cover.toFixed(1)}D</span>
          </span>
        )}
        {wowText != null && sel && (
          <span className="chip gap-1" title={`week ending ${sel.asof}`}>
            WoW <span className={`numeric ${wowCls}`}>{wowText}</span>
          </span>
        )}
        <span className="flex-1" />
        {data.provenance && <ProvenanceChip prov={data.provenance} />}
      </div>
      <div className="flex items-center gap-3 px-2 pb-1">
        {SERIES_TABS.map((t) => {
          const present = data.series?.[t.key] != null;
          const active = t.key === selKey;
          return (
            <button
              key={t.key}
              type="button"
              disabled={!present}
              onClick={() => setSelKey(t.key)}
              className={`font-mono text-[11px] tracking-wide ${
                active
                  ? "text-gold"
                  : present
                    ? "text-ink-faint hover:text-ink-dim"
                    : "text-ink-faint/40"
              }`}
            >
              {t.label}
            </button>
          );
        })}
        {sel && (
          <span className="ml-auto font-mono text-[11px] text-ink-faint">
            <span className="numeric text-ink">{fmtKbbl(sel.latest_kbbl)}</span> kbbl ·{" "}
            <span className="numeric">{sel.asof}</span>
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1 px-2 pb-2">
        {sel ? (
          <StocksChart series={sel} />
        ) : (
          <EmptyState feedNote="SERIES NOT IN PAYLOAD" />
        )}
      </div>
    </div>
  );
}
