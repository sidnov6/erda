"""Memo rendering (§10.6): one page, verdict + EMV headline, six sections,
red-team box, full citation appendix. The renderer interpolates — it computes
nothing (§0 rule 3)."""

from __future__ import annotations

from erda_agents.memo_schema import Memo

_SECTION_TITLES = {
    "geoscience": "Geoscience",
    "fiscal": "Fiscal",
    "political_risk": "Political Risk",
    "infrastructure": "Infrastructure & Development Concept",
    "environment": "Environment",
    "financeability": "Financeability",
    "economist": "Economics",
}


def memo_markdown(memo: Memo) -> str:
    basis = memo.verdict_basis
    lines = [
        f"# Feasibility Memo — {memo.block_id}",
        "",
        f"**Verdict: {memo.verdict}** · EMV **{basis.emv_musd:,.1f} $MM** · "
        f"P(EMV>0) **{basis.p_emv_positive:.0%}** · Pg **{basis.pg:.2f}** "
        f"({basis.pg_provenance})",
        "",
        f"_Generated {memo.generated_at} · {memo.snapshot_note} · "
        f"citation coverage {memo.citation_coverage:.0%} · "
        f"determinism hash `{memo.quant_hash[:16]}…`_",
        "",
    ]
    order = list(_SECTION_TITLES)
    for section in sorted(memo.sections, key=lambda s: order.index(s.agent)):
        lines.append(f"## {_SECTION_TITLES[section.agent]}")
        lines.append("")
        lines.append(section.narrative.strip())
        if section.quant:
            lines.append("")
            for key, field in section.quant.items():
                unit = f" {field.unit}" if field.unit else ""
                cites = ", ".join(field.source_ids)
                lines.append(f"- **{key}**: {field.value}{unit} _[{cites}]_")
        lines.append("")
    lines += [
        "## Red Team — what would make this wrong",
        "",
        memo.redteam_narrative.strip(),
        "",
        "## Citation appendix",
        "",
    ]
    seen: dict[str, list[str]] = {}
    for section in memo.sections:
        for key, field in section.quant.items():
            for source_id in field.source_ids:
                seen.setdefault(source_id, []).append(f"{section.agent}.{key}")
    for source_id in sorted(seen):
        lines.append(f"- `{source_id}` ← {', '.join(sorted(set(seen[source_id])))}")
    lines.append("")
    lines.append(
        "_Screening tool — ranks resemblance and economics at area level; not "
        "seismic; never \"oil is here.\"_"
    )
    return "\n".join(lines)
