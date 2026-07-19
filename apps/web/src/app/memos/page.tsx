"use client";

/**
 * Memo viewer (§8.11): list + one-page memo with citation chips, coverage
 * gauge, verdict, determinism hash. Same design system as the terminal.
 */

import Link from "next/link";
import { useState } from "react";

import { SeismicDivider } from "@/components/SeismicDivider";
import { useErda } from "@/lib/api";

interface MemoListItem {
  block_id: string;
  verdict: string;
  emv_musd: number;
  generated_at: string;
  citation_coverage: number;
  narrator: string | null;
}

interface QuantField {
  value: number | string | boolean;
  unit: string | null;
  source_ids: string[];
}

interface MemoRecord {
  memo: {
    block_id: string;
    generated_at: string;
    snapshot_note: string;
    verdict: string;
    verdict_basis: {
      emv_musd: number;
      p_emv_positive: number;
      sanctions_flag: boolean;
      wdpa_overlap_pct: number;
      pg: number;
      pg_provenance: string;
    };
    sections: { agent: string; narrative: string; quant: Record<string, QuantField> }[];
    redteam_narrative: string;
    citation_coverage: number;
    quant_hash: string;
  };
  narrator: string;
}

const SECTION_TITLES: Record<string, string> = {
  geoscience: "Geoscience",
  fiscal: "Fiscal",
  political_risk: "Political risk",
  infrastructure: "Infrastructure & dev concept",
  environment: "Environment",
  financeability: "Financeability",
  economist: "Economics",
};

const VERDICT_CLS: Record<string, string> = {
  GO: "text-oil",
  CONDITIONAL: "text-ink",
  NO_GO: "text-warn",
};

function MemoView({ blockId }: { blockId: string }) {
  const { data } = useErda<MemoRecord>(`memos/${blockId}`, 300_000);
  if (!data) {
    return <span className="chip text-ink-faint">LOADING {blockId}</span>;
  }
  const m = data.memo;
  const b = m.verdict_basis;
  return (
    <article className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`chip ${VERDICT_CLS[m.verdict] ?? "text-ink"}`}>
          VERDICT {m.verdict.replace("_", "-")}
        </span>
        <span className="chip">
          EMV&nbsp;<span className="numeric text-ink">{b.emv_musd.toLocaleString()}</span> $MM
        </span>
        <span className="chip">
          P(EMV&gt;0)&nbsp;<span className="numeric text-ink">{(b.p_emv_positive * 100).toFixed(0)}%</span>
        </span>
        <span className="chip" title={b.pg_provenance}>
          Pg&nbsp;<span className="numeric text-ink">{b.pg.toFixed(2)}</span> · USER-SUPPLIED
        </span>
        <span className="chip text-ink-faint" title="quantitative-core determinism hash (§11.3)">
          #{m.quant_hash.slice(0, 12)}
        </span>
        <span
          className={`chip ${m.citation_coverage >= 0.9 ? "text-oil" : "text-warn"}`}
          title="cited quantitative fields ÷ total (§10.3, Chair rejects < 0.9)"
        >
          CITED {(m.citation_coverage * 100).toFixed(0)}%
        </span>
        {data.narrator === "TemplateNarrator" && (
          <span className="chip text-warn" title="no LLM key configured at generation time">
            TEMPLATE NARRATION
          </span>
        )}
        {data.narrator === "GroqNarrator" && (
          <span
            className="chip text-ink-faint"
            title="owner-authorized stack deviation: Groq (llama-3.3-70b) at temperature 0 in place of the Claude API. The quant hash excludes prose."
          >
            GROQ NARRATION
          </span>
        )}
      </div>

      {[...m.sections]
        .sort(
          (a, b) =>
            Object.keys(SECTION_TITLES).indexOf(a.agent) -
            Object.keys(SECTION_TITLES).indexOf(b.agent)
        )
        .map((s) => (
        <section key={s.agent} className="panel">
          <div className="flex items-center gap-2 px-2 pb-1 pt-2">
            <h2 className="panel-title">{SECTION_TITLES[s.agent] ?? s.agent}</h2>
          </div>
          <SeismicDivider />
          <div className="px-2 pb-2 pt-1">
            <p className="max-w-[85ch] text-[12px] leading-5 text-ink-dim">{s.narrative}</p>
            {Object.keys(s.quant).length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(s.quant).map(([key, field]) => (
                  <span
                    key={key}
                    className="chip"
                    title={`sources: ${field.source_ids.join(", ")}`}
                  >
                    {key}{" "}
                    <span className="numeric text-ink">
                      {typeof field.value === "number"
                        ? field.value.toLocaleString()
                        : String(field.value)}
                    </span>
                    {field.unit ? <span className="text-ink-faint"> {field.unit}</span> : null}
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>
      ))}

      <section className="panel border-warn/40">
        <div className="flex items-center gap-2 px-2 pb-1 pt-2">
          <h2 className="panel-title">Red team — what would make this wrong</h2>
        </div>
        <SeismicDivider />
        <p className="max-w-[85ch] px-2 pb-2 pt-1 text-[12px] leading-5 text-ink-dim">
          {m.redteam_narrative}
        </p>
      </section>

      <p className="text-[11px] text-ink-faint">{m.snapshot_note}</p>
    </article>
  );
}

export default function MemosPage() {
  const { data } = useErda<{ memos: MemoListItem[] }>("memos", 120_000);
  const [selected, setSelected] = useState<string | null>(null);
  const memos = data?.memos ?? [];
  const active = selected ?? memos[0]?.block_id ?? null;

  return (
    <div className="min-h-full bg-bg0">
      <header className="sticky top-0 z-10 flex h-10 items-center gap-3 border-b border-line bg-bg0 px-4">
        <span className="font-mono text-[13px] text-gold">ERDA&gt;</span>
        <span className="font-mono text-[13px] text-ink">MEMO</span>
        <span className="panel-title text-ink-dim">Feasibility memos</span>
        <div className="flex-1" />
        <Link href="/" className="chip hover:text-ink">
          ← TERMINAL
        </Link>
      </header>
      <main className="mx-auto flex max-w-[1100px] gap-4 px-4 py-4">
        <nav className="w-56 shrink-0">
          {memos.length === 0 && (
            <span className="chip text-ink-faint">NO MEMOS YET — ops/make_memo.py</span>
          )}
          <ul className="flex flex-col gap-1">
            {memos.map((item) => (
              <li key={item.block_id}>
                <button
                  type="button"
                  onClick={() => setSelected(item.block_id)}
                  className={`panel w-full px-2 py-1.5 text-left ${
                    active === item.block_id ? "panel--active" : ""
                  }`}
                >
                  <div className="font-mono text-[12px] text-ink">{item.block_id}</div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[11px] ${VERDICT_CLS[item.verdict] ?? "text-ink"}`}>
                      {item.verdict.replace("_", "-")}
                    </span>
                    <span className="numeric text-[11px] text-ink-dim">
                      {item.emv_musd.toLocaleString()} $MM
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0 flex-1">{active && <MemoView blockId={active} />}</div>
      </main>
    </div>
  );
}
