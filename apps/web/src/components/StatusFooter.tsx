"use client";

import { useErda } from "@/lib/api";

/**
 * Status line + honest-boundaries footer (§1) + truth badge (§15): the mode
 * chip reports what the data plane actually holds, never an aspiration.
 */
export function StatusFooter({ status }: { status: string }) {
  const { data: mode } = useErda<{ mode: string; tables?: number; frozen_at?: string }>(
    "mode",
    120_000
  );

  const modeText = mode
    ? mode.mode === "LIVE"
      ? `LIVE · ${mode.tables} TABLES`
      : mode.mode === "SNAPSHOT"
        ? `SNAPSHOT · ${mode.tables} TABLES`
        : `${mode.mode} · NO DATA`
    : "SHELL · NO DATA";
  // SNAPSHOT is a truthful state, not an error — cyan, not warn (§15).
  const modeCls =
    mode?.mode === "LIVE" ? "text-oil" : mode?.mode === "SNAPSHOT" ? "text-cyan" : "text-ink-faint";

  return (
    <footer className="flex h-8 shrink-0 items-center gap-3 border-t border-line bg-bg0 px-2">
      <span className="numeric truncate text-[11px] text-ink-dim" role="status">
        {status}
      </span>
      <div className="min-w-0 flex-1" />
      <span className="hidden truncate text-[11px] text-ink-faint md:inline">
        Screening tool — ranks resemblance to historically successful acreage. Not seismic; never
        &ldquo;oil is here.&rdquo;
      </span>
      <a
        href="/validation"
        className="chip shrink-0 text-warn"
        title="§9.8 falsification gate failed — no prospectivity map ships; model card + CV table on /validation"
      >
        MODEL: NO-GO §9.8
      </a>
      <span
        className={`chip shrink-0 ${modeCls}`}
        title={mode?.frozen_at ? `frozen ${mode.frozen_at.slice(0, 19)}Z` : undefined}
      >
        {modeText}
      </span>
      <span className="chip shrink-0 text-ink-faint">P6</span>
    </footer>
  );
}
