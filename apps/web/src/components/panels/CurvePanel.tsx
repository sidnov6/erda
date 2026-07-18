"use client";

import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type CurvePayload, useErda } from "@/lib/api";

/** CRV — placeholder integration shell; chart implementation follows. */
export function CurvePanel() {
  const { data } = useErda<CurvePayload>("panels/curve");

  if (!data || !data.available) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote="FRED · YF_CURVE — P1" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        {data.strip && (
          <span className="chip text-ink-dim">
            {data.strip.structure.toUpperCase()} · M1–M12 {data.strip.slope_m1_m12}
          </span>
        )}
        {data.strip && <ProvenanceChip prov={data.strip.provenance} label="~YF" />}
        {data.spot_provenance && <ProvenanceChip prov={data.spot_provenance} />}
      </div>
      <div className="min-h-0 flex-1 px-2 pb-1 font-mono text-[11px] text-ink-dim">
        {data.strip?.contracts.slice(0, 6).map((c) => (
          <div key={c.contract} className="flex justify-between border-b border-line/50 py-0.5">
            <span>{c.contract}</span>
            <span className="numeric text-ink">{c.settle_usd_bbl.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
