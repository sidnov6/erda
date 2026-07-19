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
  showFields,
  onToggleFields,
  showInfra,
  onToggleInfra,
  showProtected,
  onToggleProtected,
  wellCount,
  fieldCount,
}: {
  year: number;
  yearMin: number;
  yearMax: number;
  onYear: (y: number) => void;
  showFields: boolean;
  onToggleFields: () => void;
  showInfra: boolean;
  onToggleInfra: () => void;
  showProtected: boolean;
  onToggleProtected: () => void;
  wellCount: number;
  fieldCount: number;
}) {
  return (
    <>
      {/* legend + honesty note, top-left. z-20 clears the maplibre control layer;
          opaque bg so no coastline shows through the swatches (esp. green oil). */}
      <div className="pointer-events-none absolute left-3 top-3 z-20 flex flex-col gap-1">
        <div className="pointer-events-auto flex items-center gap-3 border border-line bg-bg1 pl-3 pr-2 py-1">
          <LegendDot color="var(--oil)" label="oil" />
          <LegendDot color="var(--gas)" label="gas" />
          <LegendDot color="rgb(90,120,105)" label="disc" />
          <LegendDot color="var(--dry)" label="dry" />
          <span className="numeric text-[11px] text-ink-faint">
            {wellCount.toLocaleString()} wildcats
          </span>
        </div>
        {fieldCount > 0 && (
          <div className="pointer-events-auto flex items-center gap-2 border border-line bg-bg1 pl-3 pr-2 py-1">
            <LegendDot color="var(--gold)" label="field" />
            <span className="numeric text-[11px] text-ink-faint">
              {fieldCount.toLocaleString()} global fields · GOGET
            </span>
          </div>
        )}
        <span
          className="pointer-events-auto max-w-[280px] border border-line bg-bg1 px-2 py-1 font-mono text-[11px] leading-4 text-ink-faint"
          title="/validation → model validation"
        >
          Gold = known fields worldwide (GEM). Green/red/grey = wildcat outcomes
          (5 open regulators). NO prospectivity heatmap — §9.8 gate failed.
        </span>
      </div>

      {/* layer toggles, top-right — below the maplibre zoom control, z above it */}
      <div className="absolute right-2 top-20 z-20 flex flex-col gap-1">
        <ToggleChip active={showFields} onClick={onToggleFields} label="FIELDS" />
        <ToggleChip active={showInfra} onClick={onToggleInfra} label="INFRA" />
        <ToggleChip active={showProtected} onClick={onToggleProtected} label="WDPA" />
      </div>

      {/* time slider, bottom — min→max reads left→right; gold readout on the left */}
      <div className="absolute bottom-2 left-2 right-2 z-20 flex items-center gap-2 border border-line bg-bg1 px-2 py-1">
        <span className="shrink-0 font-mono text-[11px] uppercase tracking-wider text-ink-faint">
          SPUD ≤
        </span>
        <span className="numeric w-11 shrink-0 text-[12px] text-gold">{year}</span>
        <span className="numeric w-8 shrink-0 text-right text-[11px] text-ink-faint">{yearMin}</span>
        <input
          type="range"
          min={yearMin}
          max={yearMax}
          value={year}
          onChange={(e) => onYear(Number(e.target.value))}
          className="erda-slider min-w-0 flex-1"
          aria-label="spud year filter"
        />
        <span className="numeric w-8 shrink-0 text-[11px] text-ink-faint">{yearMax}</span>
      </div>
    </>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex shrink-0 items-center gap-1">
      <span
        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
        style={{ background: color }}
      />
      <span className="font-mono text-[11px] text-ink-dim">{label}</span>
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
      className={`chip bg-bg1 ${active ? "border-gold text-gold" : "text-ink-dim"}`}
    >
      {label}
    </button>
  );
}
