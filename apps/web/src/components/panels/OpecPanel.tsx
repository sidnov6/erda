"use client";

import { useMemo, useState } from "react";
import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type OpecPayload, type OpecRow, useErda } from "@/lib/api";

/**
 * OPEC — compliance table (spec §8.5). Dense sortable grid: MOMR secondary-source
 * production vs curated ONOMM required-production targets. Extraction is
 * semi-automated (table transcribed from MOMR image assets) — flagged honestly
 * with an ink-faint chip per §4. Under-production vs target is data, not an
 * alert: bars stay --dry, numbers stay --ink, --warn never appears here.
 */

type SortKey = "country" | "target" | "prod" | "pct";
type SortDir = "asc" | "desc";

const COLS: { key: SortKey; label: string; right: boolean }[] = [
  { key: "country", label: "COUNTRY", right: false },
  { key: "target", label: "TARGET", right: true },
  { key: "prod", label: "PROD", right: true },
  { key: "pct", label: "% OF TGT", right: true },
];

/** Bar scale ceiling: min(pct, 120) mapped onto the fixed track width. */
const PCT_SCALE_MAX = 120;

function sortValue(row: OpecRow, key: SortKey): string | number | null {
  switch (key) {
    case "country":
      return row.country;
    case "target":
      return row.target_kbd;
    case "prod":
      return row.production_kbd;
    case "pct":
      return row.pct_of_target;
  }
}

/** Notes keyword for countries with no target (EXEMPT / EXITED), else null. */
function statusKeyword(notes: string): string | null {
  if (/exempt/i.test(notes)) return "EXEMPT";
  if (/exit/i.test(notes)) return "EXITED";
  return null;
}

const kbd = (v: number) =>
  v.toLocaleString("en-US", { maximumFractionDigits: 0 });

export function OpecPanel() {
  const { data } = useErda<OpecPayload>("panels/opec", 300_000);
  const [sortKey, setSortKey] = useState<SortKey>("prod");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const rows = useMemo(() => {
    const src = data?.rows ?? [];
    return [...src].sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av == null && bv == null) return 0;
      if (av == null) return 1; // nulls sink regardless of direction
      if (bv == null) return -1;
      const cmp =
        typeof av === "string"
          ? av.localeCompare(bv as string)
          : av - (bv as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, sortKey, sortDir]);

  if (!data || !data.available || !data.rows) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote={data?.reason ?? "OPEC MOMR — P1"} />
      </div>
    );
  }

  const onSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "country" ? "asc" : "desc");
    }
  };

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        {data.month && <span className="chip text-ink-dim">{data.month}</span>}
        {data.extraction && (
          <span
            className="chip text-ink-faint"
            title="Production values transcribed from MOMR table image assets — semi-automated extraction"
          >
            {data.extraction.replace(/_/g, "-").toUpperCase()}
          </span>
        )}
        {data.production_provenance && (
          <ProvenanceChip prov={data.production_provenance} label="MOMR" />
        )}
        {data.targets_provenance && (
          <ProvenanceChip prov={data.targets_provenance} label="TARGETS" />
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-1">
        <table className="w-full border-separate border-spacing-0 text-[11px]">
          <thead>
            <tr>
              {COLS.map((c) => {
                const active = sortKey === c.key;
                return (
                  <th
                    key={c.key}
                    onClick={() => onSort(c.key)}
                    aria-sort={
                      active
                        ? sortDir === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                    className={`sticky top-0 z-10 cursor-pointer select-none border-b border-line bg-bg1 py-1 font-mono text-[10px] font-normal uppercase tracking-wider ${
                      active ? "text-ink-dim" : "text-ink-faint"
                    } ${c.right ? "pl-2 text-right" : "pr-2 text-left"}`}
                  >
                    {c.label}
                    <span
                      aria-hidden="true"
                      className={active ? "text-gold" : "text-transparent"}
                    >
                      {" "}
                      {active && sortDir === "asc" ? "▴" : "▾"}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const kw = r.target_kbd == null ? statusKeyword(r.notes) : null;
              return (
                <tr key={r.country} title={r.notes || undefined}>
                  <td className="border-b border-line/50 py-[3px] pr-2 text-ink-dim">
                    {r.country}
                    {kw && (
                      <span className="chip ml-1 h-[13px] px-1 text-[9px] text-ink-faint">
                        {kw}
                      </span>
                    )}
                  </td>
                  <td className="numeric border-b border-line/50 py-[3px] pl-2 text-right">
                    {r.target_kbd != null ? (
                      <span className="text-ink">{kbd(r.target_kbd)}</span>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                  <td className="numeric border-b border-line/50 py-[3px] pl-2 text-right text-ink">
                    {kbd(r.production_kbd)}
                  </td>
                  <td className="border-b border-line/50 py-[3px] pl-2">
                    {r.pct_of_target != null ? (
                      <span className="flex items-center justify-end gap-1.5">
                        <span className="h-[3px] w-9 shrink-0 bg-line/40">
                          <span
                            className="block h-full bg-dry"
                            style={{
                              width: `${(Math.min(r.pct_of_target, PCT_SCALE_MAX) / PCT_SCALE_MAX) * 100}%`,
                            }}
                          />
                        </span>
                        <span className="numeric text-ink">
                          {r.pct_of_target.toFixed(1)}
                        </span>
                      </span>
                    ) : (
                      <span className="block text-right text-ink-faint">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
