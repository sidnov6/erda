/**
 * Honest unconnected state (§0 rule 4: never fabricate): a corner chip naming
 * the real sources and the phase they connect in. The panel body behind it draws
 * its ghost frame (PanelGhost) — structure, never values.
 */
export function EmptyState({ feedNote, feedDetail }: { feedNote: string; feedDetail?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1 px-2 pb-1">
      <span className="chip text-ink-faint">AWAITING FEED</span>
      <span
        className="chip max-w-full truncate border-transparent text-ink-faint/80"
        title={feedDetail ?? feedNote}
      >
        {feedNote}
      </span>
    </div>
  );
}
