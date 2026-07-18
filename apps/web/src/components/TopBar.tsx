/**
 * Command bar + ticker tape (§8.1). P0: the ticker carries no values — feeds
 * connect in P1 — so every instrument shows an em-dash, never a made-up number.
 */
const TICKER_INSTRUMENTS = ["BRENT", "WTI", "B–W", "3-2-1", "M1–M12", "RIGS"];

export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
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
      <span className="chip px-1 py-px text-[10px] leading-4">⌘K</span>
      <div className="min-w-0 flex-1" />
      <div className="flex items-center gap-4 overflow-hidden whitespace-nowrap">
        <span className="chip px-1 py-px text-[10px] leading-4 text-ink-faint">
          FEEDS OFFLINE · P1
        </span>
        {TICKER_INSTRUMENTS.map((name) => (
          <span key={name} className="flex items-baseline gap-1.5">
            <span className="font-mono text-[11px] text-ink-dim">{name}</span>
            <span className="numeric text-[12px] text-ink-faint">—</span>
          </span>
        ))}
      </div>
    </header>
  );
}
