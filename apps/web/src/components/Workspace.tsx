"use client";

import { useEffect, useState } from "react";
import GridLayout, { useContainerWidth } from "react-grid-layout";

import { EmptyState } from "./EmptyState";
import { Panel } from "./Panel";
import { PanelGhost } from "./PanelGhost";
import dynamic from "next/dynamic";

import { CurvePanel } from "./panels/CurvePanel";
import { DiscoveryPanel } from "./panels/DiscoveryPanel";
import { EventsPanel } from "./panels/EventsPanel";
import { InventoriesPanel } from "./panels/InventoriesPanel";
import { OpecPanel } from "./panels/OpecPanel";

// deck.gl + maplibre are browser-only and heavy — load client-side, no SSR.
const MapHero = dynamic(() => import("./map/MapHero").then((m) => m.MapHero), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center font-mono text-[11px] text-ink-faint">
      LOADING MAP…
    </div>
  ),
});
import type { SourceStatus } from "@/lib/api";
import { PANELS, type PanelDef, type PanelId } from "@/lib/registry";

const LAYOUT = PANELS.map((p) => ({ i: p.id, ...p.layout }));

/** Total rows in the default layout (§13.2): columns of 6+5+5 beside a 16-row hero. */
const ROWS = 16;
const GAP = 8;
const PAD = 8;

/** P1: live panel bodies. DISC/RANK/MAP keep their ghosts until P2/P3. */
const LIVE_PANELS: Partial<Record<PanelId, () => React.ReactNode>> = {
  crv: () => <CurvePanel />,
  inv: () => <InventoriesPanel />,
  opec: () => <OpecPanel />,
  events: () => <EventsPanel />,
  disc: () => <DiscoveryPanel />,
  map: () => <MapHero />,
};

function panelBody(p: PanelDef) {
  const live = LIVE_PANELS[p.id];
  if (live) return live();
  return (
    <div className="flex h-full flex-col pt-1">
      <EmptyState feedNote={p.feedNote} feedDetail={p.feedDetail} />
      <div className="min-h-0 flex-1 pb-1">
        <PanelGhost def={p} />
      </div>
    </div>
  );
}

/**
 * Draggable terminal workspace (§13.2). Drag by the panel title bar; resize from
 * the corner. Row height is derived from the viewport so the default layout fills
 * it exactly — a terminal has no dead space below the fold.
 */
export function Workspace({
  focused,
  sources,
}: {
  focused: PanelId | null;
  sources: Record<string, SourceStatus> | null;
}) {
  const { width, containerRef } = useContainerWidth();
  const [height, setHeight] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setHeight(el.clientHeight);
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    measure();
    return () => ro.disconnect();
  }, [containerRef]);

  const rowHeight =
    height > 0 ? Math.max(24, Math.floor((height - 2 * PAD - (ROWS - 1) * GAP) / ROWS)) : 40;
  // Absorb the integer-division remainder into vertical padding so the grid
  // fills the viewport exactly — no off-grid gutter above the status bar.
  const padY = height > 0 ? PAD + (height - 2 * PAD - (ROWS - 1) * GAP - ROWS * rowHeight) / 2 : PAD;

  return (
    <main ref={containerRef} className="min-h-0 flex-1 overflow-y-auto">
      {width > 0 && (
        <GridLayout
          layout={LAYOUT}
          width={width}
          gridConfig={{ cols: 12, rowHeight, margin: [GAP, GAP], containerPadding: [PAD, padY] }}
          dragConfig={{ handle: ".panel-drag" }}
        >
          {PANELS.map((p) => (
            <div key={p.id}>
              <Panel def={p} active={focused === p.id} sources={sources}>
                {panelBody(p)}
              </Panel>
            </div>
          ))}
        </GridLayout>
      )}
    </main>
  );
}
