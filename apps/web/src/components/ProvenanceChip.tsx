import type { Provenance } from "@/lib/api";

/**
 * The provenance chip (§0 rule 5, §11.1): every displayed number gets one.
 * Hover reveals source, timestamp, URL, transform version.
 */
export function ProvenanceChip({ prov, label }: { prov: Provenance; label?: string }) {
  const retrieved = prov.retrieved_at.slice(0, 16).replace("T", " ");
  return (
    <a
      href={prov.source_url.startsWith("https://") ? prov.source_url : undefined}
      target="_blank"
      rel="noreferrer"
      className="chip shrink-0 text-ink-faint hover:text-ink-dim"
      title={`${prov.source_id} · ${retrieved}Z · ${prov.source_url} · ${prov.transform_version}`}
    >
      {label ?? prov.source_id.toUpperCase()}
    </a>
  );
}

/** Freshness badge: the panel states its feed's truth, never assumes it. */
export function FreshnessBadge({
  status,
  ageDays,
}: {
  status: "pass" | "warn" | "fail" | null;
  ageDays?: number | null;
}) {
  if (status === null) {
    return <span className="chip text-ink-faint">NO FEED</span>;
  }
  const text =
    status === "pass" ? "LIVE" : status === "warn" ? "AGING" : "STALE";
  const cls =
    status === "pass" ? "text-oil" : status === "warn" ? "text-ink-dim" : "text-warn";
  return (
    <span className={`chip ${cls}`} title={ageDays != null ? `${ageDays}d old` : undefined}>
      {text}
    </span>
  );
}
