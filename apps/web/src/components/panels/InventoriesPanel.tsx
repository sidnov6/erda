"use client";

import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type InventoriesPayload, useErda } from "@/lib/api";

/** INV — placeholder integration shell; chart implementation follows. */
export function InventoriesPanel() {
  const { data } = useErda<InventoriesPayload>("panels/inventories");

  if (!data || !data.available || !data.series) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote={data?.reason ?? "EIA WPSR · JODI — P1"} />
      </div>
    );
  }

  const crude = data.series["crude_stocks_excl_spr_kbbl"];
  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        {data.days_of_cover != null && (
          <span className="chip text-ink-dim">COVER {data.days_of_cover}D</span>
        )}
        {data.provenance && <ProvenanceChip prov={data.provenance} />}
      </div>
      <div className="min-h-0 flex-1 px-2 pb-1 font-mono text-[11px] text-ink-dim">
        {crude && (
          <div className="flex justify-between py-0.5">
            <span>CRUDE EX-SPR</span>
            <span className="numeric text-ink">
              {(crude.latest_kbbl / 1000).toFixed(1)} Mbbl
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
