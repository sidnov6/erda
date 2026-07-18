"use client";

/**
 * /validation — spec §11: validation as a first-class feature.
 * A scrolling report page (not the terminal grid) rendering the nightly
 * validation report verbatim: freshness vs SLA, EIA↔JODI reconciliation,
 * WPSR recomputation, curve checks. Every number comes from /api/erda/validation
 * or /api/erda/sources — nothing is fabricated (§0 rule 4/5).
 */

import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { FreshnessBadge } from "@/components/ProvenanceChip";
import { SeismicDivider } from "@/components/SeismicDivider";
import { type SourceStatus, useErda } from "@/lib/api";

/* ————— payload shapes (narrowed from ValidationReport's loose sections) ————— */

type CheckStatus = "pass" | "warn" | "fail";

interface FreshnessRow {
  source_id: string;
  age_days: number | null;
  sla_days: number;
  retrieved_at: string | null;
  status: CheckStatus;
  detail: string;
}

interface ReconRow {
  country: string;
  month: string;
  production_kbd_eia: number;
  production_kbd_jodi: number;
  delta_pct: number;
  status: CheckStatus;
}

interface WpsrRow {
  week: string;
  stocks_kbbl: number;
  reported_change_kbbl: number;
  computed_change_kbbl: number;
  status: CheckStatus;
}

interface CurveRow {
  contract: string;
  month_index: number;
  expiry: string;
  settle_usd_bbl: number;
  stale: boolean;
  status: CheckStatus;
}

interface ValidationPayload {
  available: boolean;
  reason?: string;
  report?: {
    generated_at: string;
    transform_version: string;
    summary: { pass: number; warn: number; fail: number; overall: string };
    sections: {
      freshness: FreshnessRow[];
      eia_jodi_reconciliation: ReconRow[];
      wpsr_consistency: WpsrRow[];
      curve_checks: CurveRow[];
    };
  };
}

/* ————— formatting (presentation only; values pass through untouched) ————— */

const fmtTs = (iso: string) => `${iso.slice(0, 16).replace("T", " ")}Z`;
const fmtDay = (iso: string) => iso.slice(0, 10);
const fmtInt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmtDelta = (v: number) => {
  const r = Number(v.toFixed(2)) + 0; // drop negative zero after rounding
  return `${r > 0 ? "+" : ""}${r.toFixed(2)}%`;
};
const fmtSigned = (v: number) => `${v > 0 ? "+" : ""}${fmtInt(v)}`;

const STATUS_TEXT: Record<CheckStatus, string> = {
  pass: "text-oil",
  warn: "text-ink-dim",
  fail: "text-warn",
};
const STATUS_RANK: Record<CheckStatus, number> = { fail: 0, warn: 1, pass: 2 };

function StatusChip({ status }: { status: CheckStatus }) {
  return <span className={`chip ${STATUS_TEXT[status]}`}>{status.toUpperCase()}</span>;
}

/* ————— shared table styling (dense, hairline, tabular) ————— */

const TH = "px-2 py-1 text-left font-mono text-[11px] font-normal uppercase tracking-wider text-ink-faint";
const THR = `${TH} text-right`;
const TD = "whitespace-nowrap px-2 py-1 text-[12px] text-ink";
const TDN = `${TD} numeric text-right`;
const ROW = "border-t border-line";

function ReportPanel({
  title,
  mnemo,
  caption,
  right,
  children,
}: {
  title: string;
  mnemo: string;
  caption?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="flex items-center gap-2 px-2 pb-1 pt-2">
        <h2 className="panel-title">{title}</h2>
        {caption && <span className="text-[11px] text-ink-faint">{caption}</span>}
        <div className="flex-1" />
        {right}
        <span className="panel-mnemo text-[11px]">{mnemo}</span>
      </div>
      <SeismicDivider />
      <div className="overflow-x-auto px-2 pb-2 pt-1">{children}</div>
    </section>
  );
}

/* ————— sections ————— */

function FreshnessSection({
  rows,
  sources,
}: {
  rows: FreshnessRow[];
  sources: SourceStatus[] | null;
}) {
  const meta = new Map((sources ?? []).map((s) => [s.source_id, s]));
  return (
    <ReportPanel title="Freshness" mnemo="FRS" caption="age vs SLA per registered source">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className={TH}>Source</th>
            <th className={TH}>Name</th>
            <th className={TH}>Cadence</th>
            <th className={THR}>Age</th>
            <th className={THR}>SLA</th>
            <th className={THR}>Retrieved</th>
            <th className={TH}>Status</th>
            <th className={TH}>Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const src = meta.get(r.source_id);
            return (
              <tr key={r.source_id} className={ROW}>
                <td className={`${TD} font-mono`}>{r.source_id}</td>
                <td className={`${TD} text-ink-dim`}>{src?.name ?? "—"}</td>
                <td className={`${TD} font-mono text-ink-dim`}>{src?.cadence ?? "—"}</td>
                <td className={TDN}>{r.age_days == null ? "—" : `${r.age_days.toFixed(1)}d`}</td>
                <td className={`${TDN} text-ink-dim`}>{`${r.sla_days.toFixed(0)}d`}</td>
                <td className={`${TDN} text-ink-dim`}>
                  {r.retrieved_at ? fmtTs(r.retrieved_at) : "—"}
                </td>
                <td className={TD}>
                  <FreshnessBadge status={r.status} ageDays={r.age_days} />
                </td>
                <td className={`${TD} text-ink-faint`}>{r.detail || "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ReportPanel>
  );
}

interface CountryGroup {
  country: string;
  latest: ReconRow;
  months: ReconRow[]; // sorted desc
  tally: Record<CheckStatus, number>;
}

function ReconSection({ rows }: { rows: ReconRow[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const groups = useMemo<CountryGroup[]>(() => {
    const byCountry = new Map<string, ReconRow[]>();
    for (const r of rows) {
      const list = byCountry.get(r.country);
      if (list) list.push(r);
      else byCountry.set(r.country, [r]);
    }
    const out: CountryGroup[] = [];
    for (const [country, months] of byCountry) {
      months.sort((a, b) => (a.month < b.month ? 1 : -1));
      const tally: Record<CheckStatus, number> = { pass: 0, warn: 0, fail: 0 };
      for (const m of months) tally[m.status] += 1;
      out.push({ country, latest: months[0], months, tally });
    }
    out.sort(
      (a, b) =>
        STATUS_RANK[a.latest.status] - STATUS_RANK[b.latest.status] ||
        a.country.localeCompare(b.country)
    );
    return out;
  }, [rows]);

  return (
    <ReportPanel
      title="EIA ↔ JODI Reconciliation"
      mnemo="RCN"
      caption="monthly production kb/d, both sources side by side · pass |Δ| ≤ 5% · warn ≤ 10% · fail > 10% (Δ vs JODI)"
      right={<span className="chip text-ink-faint">{rows.length} CHECKS</span>}
    >
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className={TH} aria-label="expand" />
            <th className={TH}>Country</th>
            <th className={TH}>Latest</th>
            <th className={THR}>EIA kb/d</th>
            <th className={THR}>JODI kb/d</th>
            <th className={THR}>Δ%</th>
            <th className={TH}>Status</th>
            <th className={THR}>
              P·W·F <span className="normal-case">(months)</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => {
            const isOpen = !!open[g.country];
            return (
              <FragmentRow
                key={g.country}
                group={g}
                isOpen={isOpen}
                onToggle={() =>
                  setOpen((prev) => ({ ...prev, [g.country]: !prev[g.country] }))
                }
              />
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-ink-faint">
        DZA / KAZ / NGA gaps reflect condensate definition differences between the two
        sources, not a pipeline fault — the check reports the raw disagreement.
      </p>
    </ReportPanel>
  );
}

function FragmentRow({
  group: g,
  isOpen,
  onToggle,
}: {
  group: CountryGroup;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className={`${ROW} cursor-pointer hover:bg-bg0/60`}
        onClick={onToggle}
      >
        <td className={`${TD} w-6`}>
          <button
            type="button"
            aria-expanded={isOpen}
            aria-label={`${isOpen ? "Collapse" : "Expand"} ${g.country} month history`}
            className="font-mono text-[12px] text-ink-faint hover:text-ink"
          >
            {isOpen ? "−" : "+"}
          </button>
        </td>
        <td className={`${TD} font-mono`}>{g.country}</td>
        <td className={`${TD} font-mono text-ink-dim`}>{g.latest.month}</td>
        <td className={TDN}>{fmtInt(g.latest.production_kbd_eia)}</td>
        <td className={TDN}>{fmtInt(g.latest.production_kbd_jodi)}</td>
        <td className={TDN}>{fmtDelta(g.latest.delta_pct)}</td>
        <td className={TD}>
          <StatusChip status={g.latest.status} />
        </td>
        <td className={`${TDN} text-ink-dim`}>
          {g.tally.pass}·{g.tally.warn}·{g.tally.fail}
        </td>
      </tr>
      {isOpen && (
        <tr className={ROW}>
          <td />
          <td colSpan={7} className="px-2 pb-2 pt-1">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className={TH}>Month</th>
                  <th className={THR}>EIA kb/d</th>
                  <th className={THR}>JODI kb/d</th>
                  <th className={THR}>Δ%</th>
                  <th className={TH}>Status</th>
                </tr>
              </thead>
              <tbody>
                {g.months.map((m) => (
                  <tr key={m.month} className={ROW}>
                    <td className={`${TD} py-0.5 font-mono text-ink-dim`}>{m.month}</td>
                    <td className={`${TDN} py-0.5`}>{fmtInt(m.production_kbd_eia)}</td>
                    <td className={`${TDN} py-0.5`}>{fmtInt(m.production_kbd_jodi)}</td>
                    <td className={`${TDN} py-0.5`}>{fmtDelta(m.delta_pct)}</td>
                    <td className={`${TD} py-0.5`}>
                      <StatusChip status={m.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

const WPSR_WEEKS_SHOWN = 12;

function WpsrSection({ rows }: { rows: WpsrRow[] }) {
  const recent = useMemo(
    () =>
      [...rows]
        .sort((a, b) => (a.week < b.week ? 1 : -1))
        .slice(0, WPSR_WEEKS_SHOWN),
    [rows]
  );
  return (
    <ReportPanel
      title="WPSR Consistency"
      mnemo="WPS"
      caption="recomputation check — guards pipeline integrity"
      right={
        <span className="chip text-ink-faint">
          {recent.length} OF {rows.length} WKS
        </span>
      }
    >
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className={TH}>Week</th>
            <th className={THR}>Stocks kbbl</th>
            <th className={THR}>Reported Δ</th>
            <th className={THR}>Computed Δ</th>
            <th className={TH}>Status</th>
          </tr>
        </thead>
        <tbody>
          {recent.map((r) => (
            <tr key={r.week} className={ROW}>
              <td className={`${TD} font-mono text-ink-dim`}>{fmtDay(r.week)}</td>
              <td className={TDN}>{fmtInt(r.stocks_kbbl)}</td>
              <td className={TDN}>{fmtSigned(r.reported_change_kbbl)}</td>
              <td className={TDN}>{fmtSigned(r.computed_change_kbbl)}</td>
              <td className={TD}>
                <StatusChip status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ReportPanel>
  );
}

function CurveSection({ rows }: { rows: CurveRow[] }) {
  const ordered = useMemo(
    () => [...rows].sort((a, b) => a.month_index - b.month_index),
    [rows]
  );
  return (
    <ReportPanel
      title="Curve Checks"
      mnemo="CRV"
      caption="strip contracts — settle present, expiry ahead, not stale"
    >
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className={THR}>M</th>
            <th className={TH}>Contract</th>
            <th className={THR}>Expiry</th>
            <th className={THR}>Settle $/bbl</th>
            <th className={TH}>Stale</th>
            <th className={TH}>Status</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((r) => (
            <tr key={r.contract} className={ROW}>
              <td className={`${TDN} text-ink-dim`}>M{r.month_index}</td>
              <td className={`${TD} font-mono`}>{r.contract}</td>
              <td className={`${TDN} text-ink-dim`}>{fmtDay(r.expiry)}</td>
              <td className={TDN}>{r.settle_usd_bbl.toFixed(2)}</td>
              <td className={`${TD} font-mono ${r.stale ? "text-warn" : "text-ink-faint"}`}>
                {r.stale ? "YES" : "no"}
              </td>
              <td className={TD}>
                <StatusChip status={r.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ReportPanel>
  );
}

/* ————— summary strip ————— */

function SummaryStrip({
  summary,
}: {
  summary: { pass: number; warn: number; fail: number };
}) {
  const tiles: { label: string; count: number; cls: string }[] = [
    { label: "PASS", count: summary.pass, cls: "text-oil" },
    { label: "WARN", count: summary.warn, cls: "text-ink" },
    { label: "FAIL", count: summary.fail, cls: "text-warn" },
  ];
  return (
    <div className="grid grid-cols-3 gap-2">
      {tiles.map((t) => (
        <div key={t.label} className="panel flex items-baseline justify-between px-3 py-2">
          <span className="font-mono text-[11px] uppercase tracking-wider text-ink-dim">
            {t.label}
          </span>
          <span className={`numeric text-[13px] font-medium ${t.cls}`}>{t.count}</span>
        </div>
      ))}
    </div>
  );
}

/* ————— page ————— */

export default function ValidationPage() {
  const { data, error } = useErda<ValidationPayload>("validation", 120_000);
  const { data: sourcesData } = useErda<{ sources: SourceStatus[] }>("sources", 300_000);

  const report = data?.available ? data.report : undefined;
  const overall = report?.summary.overall;
  const overallStatus: CheckStatus =
    overall === "pass" || overall === "warn" || overall === "fail" ? overall : "fail";

  return (
    <div className="min-h-full bg-bg0">
      <header className="sticky top-0 z-10 flex h-10 items-center gap-3 overflow-x-auto whitespace-nowrap border-b border-line bg-bg0 px-4">
        <span className="font-mono text-[13px] text-gold">ERDA&gt;</span>
        <span className="font-mono text-[13px] text-ink">VAL</span>
        <span className="panel-title text-ink-dim">Validation report</span>
        {report && (
          <>
            <span className="chip numeric" title="report generated (UTC)">
              {fmtTs(report.generated_at)}
            </span>
            <span className="chip text-ink-faint" title="transform version">
              {report.transform_version}
            </span>
            <span className={`chip ${STATUS_TEXT[overallStatus]}`}>
              OVERALL {overallStatus.toUpperCase()}
            </span>
          </>
        )}
        <div className="flex-1" />
        <Link href="/" className="chip hover:text-ink">
          ← TERMINAL
        </Link>
      </header>

      <main className="mx-auto flex max-w-[1100px] flex-col gap-4 px-4 py-4">
        {!data && !error && (
          <div className="panel px-2 py-2">
            <span className="chip text-ink-faint">FETCHING /api/erda/validation</span>
          </div>
        )}
        {error && !data && (
          <div className="panel pt-1">
            <EmptyState
              feedNote={`validation feed unreachable — ${error}`}
              feedDetail="/api/erda/validation"
            />
          </div>
        )}
        {data && !data.available && (
          <div className="panel pt-1">
            <EmptyState
              feedNote={data.reason ?? "validation report not yet generated"}
              feedDetail="/api/erda/validation returned available:false"
            />
          </div>
        )}

        {report && (
          <>
            <SummaryStrip summary={report.summary} />
            <FreshnessSection
              rows={report.sections.freshness}
              sources={sourcesData?.sources ?? null}
            />
            <ReconSection rows={report.sections.eia_jodi_reconciliation} />
            <WpsrSection rows={report.sections.wpsr_consistency} />
            <CurveSection rows={report.sections.curve_checks} />
          </>
        )}
      </main>
    </div>
  );
}
