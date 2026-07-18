import { FreshnessBadge } from "./ProvenanceChip";
import { SeismicDivider } from "./SeismicDivider";
import type { SourceStatus } from "@/lib/api";
import type { PanelDef } from "@/lib/registry";

const RANK = { pass: 0, warn: 1, fail: 2 } as const;

/** Worst freshness across a panel's feeding sources; null = nothing written. */
function panelFreshness(
  def: PanelDef,
  sources: Record<string, SourceStatus> | null
): { status: "pass" | "warn" | "fail" | null; ageDays: number | null } {
  if (!def.sources || !sources) return { status: null, ageDays: null };
  let worst: "pass" | "warn" | "fail" | null = null;
  let age: number | null = null;
  for (const id of def.sources) {
    const fresh = sources[id]?.freshness;
    if (!fresh) continue;
    if (fresh.detail === "no data written") continue; // absent → NO FEED, not STALE
    if (worst === null || RANK[fresh.status] > RANK[worst]) worst = fresh.status;
    if (fresh.age_days != null && (age === null || fresh.age_days > age)) age = fresh.age_days;
  }
  return { status: worst, ageDays: age };
}

/**
 * Panel chrome per the design-system skill §3: title bar with mnemonic tag,
 * seismic-wiggle divider, body, freshness badge from the live ledger.
 */
export function Panel({
  def,
  active,
  sources,
  children,
}: {
  def: PanelDef;
  active: boolean;
  sources?: Record<string, SourceStatus> | null;
  children: React.ReactNode;
}) {
  const { status, ageDays } = panelFreshness(def, sources ?? null);
  return (
    <section
      aria-label={def.title}
      className={`panel flex h-full flex-col overflow-hidden ${active ? "panel--active" : ""}`}
    >
      <header className="panel-drag flex h-6 shrink-0 cursor-grab select-none items-center justify-between px-2">
        <h2 className="panel-title">{def.title}</h2>
        <div className="flex items-center gap-2">
          <FreshnessBadge status={status} ageDays={ageDays} />
          <span className="panel-mnemo text-[11px]">{def.mnemonic}</span>
        </div>
      </header>
      <SeismicDivider />
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}
