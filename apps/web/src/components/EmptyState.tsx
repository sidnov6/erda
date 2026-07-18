/**
 * Honest unconnected state (§0 rule 4: never fabricate). Not a loading state —
 * nothing is loading in P0 — so no skeleton, no spinner, no placeholder numbers.
 */
export function EmptyState({ feedNote, hero }: { feedNote: string; hero?: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center">
      <span
        className={`font-mono tracking-[0.14em] text-ink-faint ${hero ? "text-[12px]" : "text-[11px]"}`}
      >
        AWAITING FEED
      </span>
      <span className="font-mono text-[10px] tracking-[0.06em] text-ink-faint/70">{feedNote}</span>
    </div>
  );
}
