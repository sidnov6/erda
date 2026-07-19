"use client";

/**
 * Map overlay controls (§13.4): the spud-year time slider, layer toggles, the
 * well legend, and the honest §9.8 no-heatmap statement. Bottom-left, over the
 * basemap, in the terminal's chrome.
 */
export function MapControls({
  year,
  yearMin,
  yearMax,
  onYear,
  showInfra,
  onToggleInfra,
  showProtected,
  onToggleProtected,
  wellCount,
}: {
  year: number;
  yearMin: number;
  yearMax: number;
  onYear: (y: number) => void;
  showInfra: boolean;
  onToggleInfra: () => void;
  showProtected: boolean;
  onToggleProtected: () => void;
  wellCount: number;
}) {
  return (
    <>
      {/* legend + honesty note, top-left */}
      <div className="pointer-events-none absolute left-2 top-2 flex flex-col gap-1">
        <div className="pointer-events-auto flex items-center gap-2 border border-line bg-bg1/90 px-2 py-1">
          <LegendDot color="var(--oil)" label="oil" />
          <LegendDot color="var(--gas)" label="gas" />
          <LegendDot color="rgb(90,120,105)" label="disc" />
          <LegendDot color="var(--dry)" label="dry" />
          <span className="numeric text-[10px] text-ink-faint">{wellCount.toLocaleString()} wells</span>
        </div>
        <span
          className="pointer-events-auto max-w-[240px] border border-line bg-bg1/90 px-2 py-1 font-mono text-[9px] leading-3 text-ink-faint"
          title="/validation → model validation"
        >
          NO PROSPECTIVITY HEATMAP — §9.8 gate failed. Wells + context only.
        </span>
      </div>

      {/* layer toggles, top-right under nav */}
      <div className="absolute right-12 top-2 flex flex-col gap-1">
        <ToggleChip active={showInfra} onClick={onToggleInfra} label="INFRA" />
        <ToggleChip active={showProtected} onClick={onToggleProtected} label="WDPA" />
      </div>

      {/* time slider, bottom */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center gap-2 border border-line bg-bg1/90 px-2 py-1">
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">SPUD ≤</span>
        <span className="numeric w-10 text-[12px] text-gold">{year}</span>
        <input
          type="range"
          min={yearMin}
          max={yearMax}
          value={year}
          onChange={(e) => onYear(Number(e.target.value))}
          className="erda-slider min-w-0 flex-1"
          aria-label="spud year filter"
        />
        <span className="numeric text-[10px] text-ink-faint">{yearMin}</span>
      </div>
    </>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
      <span className="font-mono text-[10px] text-ink-dim">{label}</span>
    </span>
  );
}

function ToggleChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`chip ${active ? "border-gold text-gold" : "text-ink-dim"}`}
    >
      {label}
    </button>
  );
}
