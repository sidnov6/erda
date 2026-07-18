"use client";

import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type OpecPayload, useErda } from "@/lib/api";

/** OPEC — placeholder integration shell; dense grid implementation follows. */
export function OpecPanel() {
  const { data } = useErda<OpecPayload>("panels/opec", 300_000);

  if (!data || !data.available || !data.rows) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote={data?.reason ?? "OPEC MOMR — P1"} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        <span className="chip text-ink-dim">{data.month}</span>
        <span className="chip text-ink-faint">SEMI-AUTOMATED</span>
        {data.production_provenance && <ProvenanceChip prov={data.production_provenance} />}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-1 font-mono text-[11px]">
        {data.rows.slice(0, 8).map((r) => (
          <div key={r.country} className="flex justify-between border-b border-line/50 py-0.5">
            <span className="text-ink-dim">{r.country}</span>
            <span className="numeric text-ink">{r.production_kbd.toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
