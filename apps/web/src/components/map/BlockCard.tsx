"use client";

/**
 * Right-rail block card (§13.4): the picked block, its user-supplied screening
 * assumptions (Pg is user-supplied — §9.8, no model Pg), and the Generate-memo
 * action that streams committee progress over SSE, then links to the memo.
 *
 * Pg, resource triple, well cost are SCENARIO INPUTS the analyst sets — the map
 * never invents a probability. That is stated on the card.
 */

import Link from "next/link";
import { useRef, useState } from "react";

export interface PickedBlock {
  lon: number;
  lat: number;
}

const AGENT_LABELS: Record<string, string> = {
  geoscience: "Geoscience",
  fiscal: "Fiscal",
  political_risk: "Political risk",
  infrastructure: "Infrastructure",
  environment: "Environment",
  financeability: "Financeability",
  economist: "Economist",
  redteam: "Red team",
  chair: "Chair",
};

type Phase = "form" | "streaming" | "done" | "error";

export function BlockCard({ block, onClose }: { block: PickedBlock; onClose: () => void }) {
  const [iso3, setIso3] = useState("NOR");
  const [pg, setPg] = useState(0.25);
  const [wellCost, setWellCost] = useState(90);
  const [phase, setPhase] = useState<Phase>("form");
  const [progress, setProgress] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const blockId = useRef(`BLOCK-${block.lat.toFixed(2)}_${block.lon.toFixed(2)}`).current;

  async function generate() {
    setPhase("streaming");
    setProgress([]);
    setError(null);
    try {
      const resp = await fetch("/api/erda/memo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          block_id: blockId,
          lat: block.lat,
          lon: block.lon,
          iso3,
          country_name: iso3,
          host_distance_km: 120,
          pg,
          resource_p90: 60,
          resource_p50: 110,
          resource_p10: 202,
          well_cost_musd: wellCost,
        }),
      });
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop() ?? "";
        for (const ev of events) {
          const line = ev.replace(/^data: /, "").trim();
          if (!line) continue;
          const msg = JSON.parse(line) as { type: string; agent?: string; detail?: string };
          if (msg.type === "node" && msg.agent) {
            setProgress((p) => [...p, msg.agent as string]);
          } else if (msg.type === "memo") {
            setPhase("done");
          } else if (msg.type === "error") {
            setError(msg.detail ?? "committee error");
            setPhase("error");
          }
        }
      }
      setPhase((p) => (p === "streaming" ? "done" : p));
    } catch (err) {
      setError(err instanceof Error ? err.message : "request failed");
      setPhase("error");
    }
  }

  return (
    <div className="absolute right-2 top-2 z-10 flex w-64 flex-col gap-2 border border-line bg-bg1/95 p-2">
      <div className="flex items-center justify-between">
        <span className="panel-title text-ink">BLOCK PICK</span>
        <button type="button" onClick={onClose} className="chip text-ink-faint hover:text-ink">
          ✕
        </button>
      </div>
      <div className="numeric text-[11px] text-ink-dim">
        {block.lat.toFixed(3)}, {block.lon.toFixed(3)}
      </div>

      {phase === "form" && (
        <>
          <label className="flex items-center justify-between text-[11px] text-ink-dim">
            JURISDICTION
            <input
              value={iso3}
              onChange={(e) => setIso3(e.target.value.toUpperCase().slice(0, 3))}
              className="numeric w-14 border border-line bg-bg0 px-1 text-ink"
            />
          </label>
          <label className="flex items-center justify-between text-[11px] text-ink-dim">
            Pg (user-supplied)
            <input
              type="number"
              step="0.05"
              min="0.01"
              max="0.99"
              value={pg}
              onChange={(e) => setPg(Number(e.target.value))}
              className="numeric w-14 border border-line bg-bg0 px-1 text-ink"
            />
          </label>
          <label className="flex items-center justify-between text-[11px] text-ink-dim">
            WELL COST $MM
            <input
              type="number"
              step="10"
              value={wellCost}
              onChange={(e) => setWellCost(Number(e.target.value))}
              className="numeric w-14 border border-line bg-bg0 px-1 text-ink"
            />
          </label>
          <p className="font-mono text-[9px] leading-3 text-ink-faint">
            Pg is a scenario input — no model Pg ships (§9.8). Resource P90/P50/P10 use a demo triple.
          </p>
          <button
            type="button"
            onClick={generate}
            className="chip border-gold text-gold hover:bg-line/40"
          >
            GENERATE MEMO ▸
          </button>
        </>
      )}

      {(phase === "streaming" || phase === "done") && (
        <ul className="flex flex-col gap-0.5">
          {Object.keys(AGENT_LABELS).map((agent) => {
            const seen = progress.includes(agent);
            return (
              <li
                key={agent}
                className={`flex items-center gap-2 font-mono text-[11px] ${
                  seen ? "text-oil" : "text-ink-faint"
                }`}
              >
                <span>{seen ? "✓" : "·"}</span>
                {AGENT_LABELS[agent]}
              </li>
            );
          })}
        </ul>
      )}

      {phase === "done" && (
        <Link href="/memos" className="chip border-gold text-gold hover:bg-line/40">
          VIEW MEMO ▸
        </Link>
      )}

      {phase === "error" && (
        <p className="border border-warn/40 px-2 py-1 font-mono text-[10px] text-warn">
          {error}
        </p>
      )}
    </div>
  );
}
