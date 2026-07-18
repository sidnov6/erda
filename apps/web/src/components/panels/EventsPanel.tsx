"use client";

import { EmptyState } from "../EmptyState";
import { ProvenanceChip } from "../ProvenanceChip";
import { type Provenance, useErda } from "@/lib/api";

interface EventsPayload {
  available: boolean;
  reason?: string;
  provenance?: Provenance;
  events?: { seen_at: string | null; title: string | null; url: string | null; domain: string | null }[];
}

/** GDELT feed — renders the honest reason while the source is throttled. */
export function EventsPanel() {
  const { data } = useErda<EventsPayload>("panels/events", 120_000);

  if (!data || !data.available) {
    return (
      <div className="flex h-full flex-col pt-1">
        <EmptyState feedNote="GDELT — P1" />
        {data?.reason && (
          <p className="px-2 pt-1 font-mono text-[10px] leading-4 text-ink-faint/80">
            {data.reason}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col pt-1">
      <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
        {data.provenance && <ProvenanceChip prov={data.provenance} />}
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto px-2 pb-1">
        {data.events?.map((ev, i) => (
          <li key={i} className="flex items-baseline gap-2 border-b border-line/50 py-1">
            <span className="numeric shrink-0 text-[10px] text-ink-faint">
              {ev.seen_at ? ev.seen_at.slice(5, 16).replace("T", " ") : "——"}
            </span>
            <a
              href={ev.url ?? undefined}
              target="_blank"
              rel="noreferrer"
              className="min-w-0 flex-1 truncate text-[12px] text-ink-dim hover:text-ink"
            >
              {ev.title ?? "(untitled)"}
            </a>
            <span className="shrink-0 font-mono text-[10px] text-ink-faint">{ev.domain}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
