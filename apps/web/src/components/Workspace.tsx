"use client";

import { useEffect, useState } from "react";
import GridLayout, { useContainerWidth } from "react-grid-layout";

import { EmptyState } from "./EmptyState";
import { Panel } from "./Panel";
import { PanelGhost } from "./PanelGhost";
import { PANELS, type PanelId } from "@/lib/registry";

const LAYOUT = PANELS.map((p) => ({ i: p.id, ...p.layout }));

/** Total rows in the default layout (§13.2): columns of 6+5+5 beside a 16-row hero. */
const ROWS = 16;
const GAP = 8;
const PAD = 8;

/**
 * Draggable terminal workspace (§13.2). Drag by the panel title bar; resize from
 * the corner. Row height is derived from the viewport so the default layout fills
 * it exactly — a terminal has no dead space below the fold. Layout presets
 * (MARKET / EXPLORE / MEMO / VAL) arrive with real panels in later phases.
 */
export function Workspace({ focused }: { focused: PanelId | null }) {
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
              <Panel def={p} active={focused === p.id}>
                <div className="flex h-full flex-col pt-1">
                  <EmptyState feedNote={p.feedNote} feedDetail={p.feedDetail} />
                  <div className="min-h-0 flex-1 pb-1">
                    <PanelGhost def={p} />
                  </div>
                </div>
              </Panel>
            </div>
          ))}
        </GridLayout>
      )}
    </main>
  );
}
