import type { PanelDef } from "@/lib/registry";

/**
 * Ghost skeletons: each panel draws its future instrument frame in --line
 * hairlines while awaiting its feed (design-system checklist item 9 — skeletons,
 * never placeholders). Structure and schema only; a value, curve shape, or bar
 * height would be fabricated data (§0 rule 4), so none appear. Nothing animates.
 */

function ChartGhost() {
  return (
    <svg
      className="h-full w-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {/* axis rails */}
      <path d="M10 4 V88 H98" fill="none" stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      {/* ghost gridlines */}
      {[25, 46, 67].map((y) => (
        <line
          key={y}
          x1="10"
          y1={y}
          x2="98"
          y2={y}
          stroke="var(--line)"
          strokeWidth="1"
          strokeDasharray="1 3"
          vectorEffect="non-scaling-stroke"
          opacity="0.6"
        />
      ))}
      {/* time-axis ticks */}
      {[24, 44, 64, 84].map((x) => (
        <line
          key={x}
          x1={x}
          y1="88"
          x2={x}
          y2="91"
          stroke="var(--line)"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  );
}

function TableGhost({ columns }: { columns: string[] }) {
  return (
    <div className="flex h-full flex-col overflow-hidden px-2">
      <div
        className="grid h-6 shrink-0 items-center gap-2 border-b border-line"
        style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}
      >
        {columns.map((c) => (
          <span key={c} className="truncate font-mono text-[10px] tracking-[0.08em] text-ink-faint">
            {c}
          </span>
        ))}
      </div>
      {/* overdraw rows; the overflow-hidden root clips to the panel height */}
      {Array.from({ length: 24 }, (_, i) => (
        <div key={i} className="h-6 shrink-0 border-b border-line/50" />
      ))}
    </div>
  );
}

function FeedGhost() {
  const widths = ["72%", "58%", "66%", "48%", "62%"];
  return (
    <div className="h-full overflow-hidden px-2">
      {/* 16px pitch: 8px bar + 8px gap; overdrawn rows clip at the panel edge */}
      {Array.from({ length: 24 }, (_, i) => (
        <div key={i} className="flex h-4 items-center gap-2">
          <span className="h-2 w-12 shrink-0 bg-line/70" />
          <span className="h-2 bg-line/40" style={{ width: widths[i % widths.length] }} />
        </div>
      ))}
    </div>
  );
}

function MapGhost() {
  return (
    <div className="relative h-full w-full">
      <svg
        className="h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {/* graticule */}
        {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((p) => (
          <g key={p}>
            <line x1={p} y1="0" x2={p} y2="100" stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" opacity={p === 50 ? 0.9 : 0.45} />
            <line x1="0" y1={p} x2="100" y2={p} stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" opacity={p === 50 ? 0.9 : 0.45} />
          </g>
        ))}
      </svg>
      {/* scale-bar ghost */}
      <svg className="absolute bottom-3 left-3" width="96" height="10" aria-hidden="true">
        <path d="M0 2 V8 H24 V2 M24 8 H48 V2 M48 8 H72 V2 M72 8 H96 V2" fill="none" stroke="var(--dry)" strokeWidth="1" />
      </svg>
      {/* reserved memo affordance (§13.2) — disabled until the committee lands */}
      <span className="chip absolute bottom-3 right-3 text-ink-faint">
        GENERATE MEMO FOR BLOCK — P5
      </span>
    </div>
  );
}

export function PanelGhost({ def }: { def: PanelDef }) {
  switch (def.kind) {
    case "chart":
      return <ChartGhost />;
    case "table":
      return <TableGhost columns={def.columns ?? []} />;
    case "feed":
      return <FeedGhost />;
    case "map":
      return <MapGhost />;
  }
}
