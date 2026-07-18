"use client";

/**
 * Command bar + ticker tape (§8.1). Values come only from /api/panels/ticker
 * with provenance attached; instruments the API can't serve yet keep an honest
 * em-dash. Deltas follow the token convention: up = --oil, down = --gas.
 * "~" marks indicative values from the unofficial yfinance source (§4).
 */

import { type TickerInstrument, useErda } from "@/lib/api";

const PLACEHOLDER_INSTRUMENTS = ["BRENT", "WTI", "B–W", "3-2-1", "M1–M12", "US RIGS", "USD·BROAD"];

function Delta({ delta }: { delta?: number | null }) {
  if (delta == null || delta === 0) return null;
  const up = delta > 0;
  const abs = Math.abs(delta);
  // Native precision: integer series (rig counts) never grow fake decimals.
  const text = Number.isInteger(delta) ? abs.toFixed(0) : abs.toFixed(abs >= 10 ? 1 : 2);
  return (
    <span className={`numeric text-[11px] ${up ? "text-oil" : "text-gas"}`}>
      {up ? "▲" : "▼"}
      {text}
    </span>
  );
}

export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { data } = useErda<{ available: boolean; instruments?: TickerInstrument[] }>(
    "panels/ticker"
  );
  const instruments = data?.available ? (data.instruments ?? []) : null;

  return (
    <header className="flex h-10 shrink-0 items-center gap-3 border-b border-line bg-bg0 px-2">
      <button
        type="button"
        onClick={onOpenPalette}
        aria-label="Open the ERDA command line"
        className="flex items-center gap-1 font-mono text-[13px] text-gold"
      >
        ERDA&gt;
        <span className="caret" aria-hidden="true" />
      </button>
      <span className="chip">⌘K</span>
      <div className="min-w-0 flex-1" />
      <div className="flex items-center gap-4 overflow-hidden whitespace-nowrap">
        {instruments === null && (
          <span className="chip text-ink-faint">FEEDS OFFLINE · P1</span>
        )}
        {instruments === null
          ? PLACEHOLDER_INSTRUMENTS.map((name) => (
              <span key={name} className="flex items-baseline gap-1.5">
                <span className="font-mono text-[11px] text-ink-dim">{name}</span>
                <span className="numeric text-[12px] text-ink-faint">—</span>
              </span>
            ))
          : instruments.map((inst) => (
              <span
                key={inst.label}
                className="flex items-baseline gap-1.5"
                title={`${inst.unit} · as of ${inst.asof} · Δ vs prior print · ${
                  inst.provenance.source_id
                } · ${inst.provenance.source_url}${
                  inst.indicative ? " · indicative (unofficial source)" : ""
                }${inst.note ? ` · ${inst.note}` : ""}`}
              >
                <span className="font-mono text-[11px] text-ink-dim">{inst.label}</span>
                <span className="numeric text-[12px] text-ink">
                  {inst.indicative ? "~" : ""}
                  {inst.value.toLocaleString("en-US", {
                    minimumFractionDigits: inst.unit === "$/bbl" ? 2 : 0,
                    maximumFractionDigits: 2,
                  })}
                </span>
                <Delta delta={inst.delta} />
              </span>
            ))}
      </div>
    </header>
  );
}
