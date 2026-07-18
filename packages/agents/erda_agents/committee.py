"""The feasibility committee (spec §10.1): LangGraph topology

    six parallel section agents → Economist → RedTeam → Chair

Hard laws enforced here:
- agents call typed tools; every quantitative memo field is built from tool
  outputs (QuantField with source_ids) — the narrator receives tool JSON and
  returns PROSE ONLY; nothing it writes can enter a quant field (§0 rule 3);
- the verdict is decided by erda_agents.verdict rules; the Chair rejects
  citation coverage < 0.9 (§10.3) and computes the §11.3 quant hash;
- a ToolDataMissing gap becomes an explicit "data_gap" quant entry — reported,
  never invented.

The narrator is injected: production uses the Claude API at temperature 0;
tests inject a deterministic template narrator. Tool execution is identical in
both — narration never changes a number.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from erda_agents import verdict as verdict_mod
from erda_agents.memo_schema import (
    MIN_CITATION_COVERAGE,
    Memo,
    MemoSection,
    QuantField,
    VerdictBasis,
    citation_coverage,
    quant_hash,
)
from erda_agents.tools import economics, geoscience, screening
from erda_agents.tools.base import SnapshotContext, ToolDataMissing

Narrator = Callable[[str, str], str]  # (system, user) -> prose


class BlockRequest(TypedDict):
    block_id: str
    lat: float
    lon: float
    iso3: str
    country_name: str
    host_distance_km: float
    pg: float
    resource_p90_p50_p10: tuple[float, float, float]
    well_cost_musd: float


class CommitteeState(TypedDict):
    request: BlockRequest
    sections: Annotated[list[MemoSection], operator.add]
    tool_payloads: Annotated[dict[str, Any], operator.or_]
    memo: Memo | None


PG_PROVENANCE = "user-supplied (§9.8 — the falsification gate failed; no model Pg ships)"

_SYSTEM = (
    "You are the {agent} member of an upstream exploration screening committee. "
    "Write 3-5 tight sentences for an investment memo section, institutional tone. "
    "Use ONLY facts present in the tool JSON given to you — you may reword and "
    "interpret, you may NOT introduce numbers, names, or claims that are not in it. "
    "If the JSON marks a data gap, state it plainly."
)


def _q(value, unit: str | None, source_ids: list[str]) -> QuantField:
    return QuantField(value=value, unit=unit, source_ids=source_ids)


def _gap_section(agent: str, exc: ToolDataMissing, narrator: Narrator) -> tuple[MemoSection, dict]:
    payload = {"data_gap": str(exc)}
    narrative = narrator(
        _SYSTEM.format(agent=agent),
        f"Tool JSON: {payload}. The snapshot lacks this data — say so and what it means.",
    )
    section = MemoSection(
        agent=agent,
        narrative=narrative,
        quant={"data_gap": _q(str(exc), None, ["snapshot"])},
    )
    return section, payload


def build_graph(ctx: SnapshotContext, narrator: Narrator):
    def geoscience_node(state: CommitteeState) -> dict:
        r = state["request"]
        model = geoscience.get_model_score(ctx, r["lat"], r["lon"])
        offsets = geoscience.get_offset_wells(ctx, r["lat"], r["lon"])
        basin = geoscience.get_basin_stats(ctx, r["lat"], r["lon"])
        payload = {"model": model, "offsets": offsets, "basin": basin}
        quant = {
            "model_status": _q(model["model_status"], None, model["source_ids"]),
            "offset_wells_100km": _q(offsets["n_wells"], "wells", offsets["source_ids"]),
            "offset_success_rate": _q(
                offsets["offset_success_rate"]
                if offsets["offset_success_rate"] is not None
                else "no labeled offsets",
                None,
                offsets["source_ids"],
            ),
            "basin": _q(basin["province_name"], None, basin["source_ids"]),
            "basin_wildcats": _q(basin["n_wildcats"], "wells", basin["source_ids"]),
        }
        narrative = narrator(_SYSTEM.format(agent="Geoscience"), f"Tool JSON: {payload}")
        return {
            "sections": [MemoSection(agent="geoscience", narrative=narrative, quant=quant)],
            "tool_payloads": {"geoscience": payload},
        }

    def fiscal_node(state: CommitteeState) -> dict:
        r = state["request"]
        try:
            regime = screening.get_fiscal_regime(ctx, r["iso3"])
            payload = {"regime": regime}
            quant = {
                "regime_type": _q(regime["regime_type"], None, regime["source_ids"]),
                "cit_rate": _q(regime["cit_rate"], "fraction", regime["source_ids"]),
                "royalty_rate": _q(
                    regime.get("royalty_rate") if regime.get("royalty_rate") is not None
                    else "none/na",
                    "fraction",
                    regime["source_ids"],
                ),
            }
            narrative = narrator(_SYSTEM.format(agent="Fiscal"), f"Tool JSON: {payload}")
            section = MemoSection(agent="fiscal", narrative=narrative, quant=quant)
        except ToolDataMissing as exc:
            section, payload = _gap_section("fiscal", exc, narrator)
        return {"sections": [section], "tool_payloads": {"fiscal": payload}}

    def political_node(state: CommitteeState) -> dict:
        r = state["request"]
        payload: dict[str, Any] = {}
        quant: dict[str, QuantField] = {}
        try:
            gov = screening.get_governance(ctx, r["iso3"])
            payload["governance"] = gov
            rl = gov["wgi_estimates"].get("RL.EST")
            if rl is not None:
                quant["wgi_rule_of_law"] = _q(rl, "estimate (−2.5…2.5)", gov["source_ids"])
            if gov.get("fsi_total") is not None:
                quant["fsi_total"] = _q(gov["fsi_total"], "index", gov["source_ids"])
        except ToolDataMissing as exc:
            payload["governance"] = {"data_gap": str(exc)}
            quant["governance_gap"] = _q(str(exc), None, ["snapshot"])
        try:
            sanc = screening.screen_sanctions(ctx, r["iso3"], r["country_name"])
            payload["sanctions"] = sanc
            quant["sanctioned"] = _q(sanc["sanctioned"], None, sanc["source_ids"])
        except ToolDataMissing as exc:
            payload["sanctions"] = {"data_gap": str(exc)}
            quant["sanctions_gap"] = _q(str(exc), None, ["snapshot"])
        narrative = narrator(_SYSTEM.format(agent="Political Risk"), f"Tool JSON: {payload}")
        return {
            "sections": [MemoSection(agent="political_risk", narrative=narrative, quant=quant)],
            "tool_payloads": {"political_risk": payload},
        }

    def infrastructure_node(state: CommitteeState) -> dict:
        r = state["request"]
        try:
            concept = economics.classify_dev_concept(
                ctx, r["lat"], r["lon"], r["host_distance_km"]
            )
            payload = {"concept": concept}
            quant = {
                "water_depth_m": _q(concept["water_depth_m"], "m", concept["source_ids"]),
                "host_distance_km": _q(
                    concept["host_distance_km"], "km", concept["source_ids"]
                ),
                "dev_concept": _q(concept["concept"], None, concept["source_ids"]),
            }
            narrative = narrator(_SYSTEM.format(agent="Infrastructure"), f"Tool JSON: {payload}")
            section = MemoSection(agent="infrastructure", narrative=narrative, quant=quant)
        except ToolDataMissing as exc:
            section, payload = _gap_section("infrastructure", exc, narrator)
        return {"sections": [section], "tool_payloads": {"infrastructure": payload}}

    def environment_node(state: CommitteeState) -> dict:
        r = state["request"]
        try:
            wdpa = screening.get_protected_overlap(ctx, r["lat"], r["lon"])
            payload = {"wdpa": wdpa}
            quant = {
                "wdpa_overlap_pct": _q(wdpa["overlap_pct"], "%", wdpa["source_ids"]),
                "protected_areas_nearby": _q(
                    len(wdpa["areas"]), "areas", wdpa["source_ids"]
                ),
            }
            narrative = narrator(_SYSTEM.format(agent="Environment"), f"Tool JSON: {payload}")
            section = MemoSection(agent="environment", narrative=narrative, quant=quant)
        except ToolDataMissing as exc:
            section, payload = _gap_section("environment", exc, narrator)
        return {"sections": [section], "tool_payloads": {"environment": payload}}

    def financeability_node(state: CommitteeState) -> dict:
        try:
            fin = screening.screen_financing(ctx)
            payload = {"financing": fin}
            quant = {
                "institutions_checked": _q(
                    fin["n_institutions_checked"], "institutions", fin["source_ids"]
                ),
                "restricting_upstream": _q(
                    fin["n_restricting_upstream"], "institutions", fin["source_ids"]
                ),
            }
            narrative = narrator(_SYSTEM.format(agent="Financeability"), f"Tool JSON: {payload}")
            section = MemoSection(agent="financeability", narrative=narrative, quant=quant)
        except ToolDataMissing as exc:
            section, payload = _gap_section("financeability", exc, narrator)
        return {"sections": [section], "tool_payloads": {"financeability": payload}}

    def economist_node(state: CommitteeState) -> dict:
        r = state["request"]
        fiscal_payload = state["tool_payloads"].get("fiscal", {})
        regime = fiscal_payload.get("regime")
        if regime is None:
            raise ToolDataMissing(
                "economist cannot run: fiscal regime missing from snapshot "
                f"({fiscal_payload.get('data_gap', 'no fiscal payload')})"
            )
        mapping = regime.get("engine_mapping") or {}
        royalty_rate = float(mapping.get("royalty_rate", regime.get("royalty_rate") or 0.0))
        cit_rate = float(mapping.get("cit_rate", regime["cit_rate"]))

        concept_payload = state["tool_payloads"].get("infrastructure", {}).get("concept")
        if concept_payload is None:
            raise ToolDataMissing("economist cannot run: dev concept missing")
        bench = concept_payload["cost_benchmarks"]

        def mid(lo_key: str, hi_key: str) -> float:
            lo, hi = bench.get(lo_key), bench.get(hi_key)
            if lo is None or hi is None:
                raise ToolDataMissing(f"cost benchmark missing {lo_key}/{hi_key}")
            return (float(lo) + float(hi)) / 2.0

        opex = mid("opex_usd_bbl_low", "opex_usd_bbl_high")
        well_cost = r["well_cost_musd"] or mid("well_cost_musd_low", "well_cost_musd_high")
        capex_per_boe = mid("capex_usd_boe_low", "capex_usd_boe_high")
        dev_capex = capex_per_boe * r["resource_p90_p50_p10"][1]  # $/boe × MMboe = $MM
        schedule = round(mid("schedule_years_low", "schedule_years_high"))

        deck = economics.get_price_deck(ctx)
        result = economics.run_economics(
            pg=r["pg"],
            pg_provenance=PG_PROVENANCE,
            resource_p90_p50_p10=r["resource_p90_p50_p10"],
            price_usd_bbl=deck["m1_usd_bbl"],
            price_provenance=deck["provenance_note"],
            royalty_rate=royalty_rate,
            cit_rate=cit_rate,
            fiscal_source_id="curated_fiscal",
            opex_usd_bbl=opex,
            well_cost_musd=well_cost,
            dev_capex_musd=dev_capex,
            cost_source_id="curated_costs",
            schedule_years=int(schedule),
        )
        payload = {"economics": result, "price_deck": deck}
        src = result["source_ids"]
        quant = {
            "pg": _q(result["pg"], "probability", ["user_supplied"]),
            "price_m1": _q(deck["m1_usd_bbl"], "$/bbl", deck["source_ids"]),
            "npv_success": _q(result["npv_success_musd"], "MUSD", src),
            "emv": _q(result["emv_musd"], "MUSD", src),
            "breakeven": _q(result["breakeven_usd_bbl"], "$/bbl", src),
            "government_take": _q(result["government_take"], "fraction", src),
            "p_emv_positive": _q(result["mc"]["p_emv_positive"], "probability", src),
            "mc_seed": _q(result["mc"]["seed"], None, src),
        }
        narrative = narrator(
            _SYSTEM.format(agent="Economist"),
            f"Tool JSON: {payload}. Note Pg is {PG_PROVENANCE}.",
        )
        return {
            "sections": [MemoSection(agent="economist", narrative=narrative, quant=quant)],
            "tool_payloads": {"economist": payload},
        }

    def redteam_node(state: CommitteeState) -> dict:
        narrative = narrator(
            "You are the Red Team of an exploration screening committee. In 4-6 blunt "
            "sentences answer: WHAT WOULD MAKE THIS WRONG? Attack the assumptions you "
            "see in the tool JSON (Pg provenance, proxy labels, cost midpoints, price "
            "volatility, data gaps). Use only facts present in the JSON.",
            f"All tool JSON: {state['tool_payloads']}",
        )
        return {
            "sections": [MemoSection(agent="redteam", narrative=narrative, quant={})],
            "tool_payloads": {},
        }

    def chair_node(state: CommitteeState) -> dict:
        r = state["request"]
        econ = state["tool_payloads"]["economist"]["economics"]
        env = state["tool_payloads"].get("environment", {})
        wdpa_pct = env.get("wdpa", {}).get("overlap_pct")
        pol = state["tool_payloads"].get("political_risk", {})
        sanctioned = pol.get("sanctions", {}).get("sanctioned", False)

        basis = VerdictBasis(
            emv_musd=econ["emv_musd"],
            p_emv_positive=econ["mc"]["p_emv_positive"],
            sanctions_flag=bool(sanctioned),
            wdpa_overlap_pct=float(wdpa_pct) if wdpa_pct is not None else 0.0,
            pg=econ["pg"],
            pg_provenance=PG_PROVENANCE,
        )
        decided = verdict_mod.decide(basis)

        sections = [s for s in state["sections"] if s.agent != "redteam"]
        redteam = next((s for s in state["sections"] if s.agent == "redteam"), None)
        coverage = citation_coverage(sections)
        if coverage < MIN_CITATION_COVERAGE:
            raise ValueError(
                f"Chair rejects memo: citation coverage {coverage:.2f} < "
                f"{MIN_CITATION_COVERAGE} (§10.3)"
            )
        if redteam is None or not redteam.narrative.strip():
            raise ValueError("Chair rejects memo: red-team section missing (§10.6)")

        memo = Memo(
            block_id=r["block_id"],
            generated_at=datetime.now(UTC).isoformat(),
            snapshot_note="frozen local snapshot — no live internet at memo time (§10.3)",
            verdict=decided,
            verdict_basis=basis,
            sections=sections,
            redteam_narrative=redteam.narrative,
            citation_coverage=round(coverage, 4),
            quant_hash=quant_hash(sections, decided, basis),
        )
        return {"memo": memo, "tool_payloads": {}}

    graph = StateGraph(CommitteeState)
    graph.add_node("geoscience", geoscience_node)
    graph.add_node("fiscal", fiscal_node)
    graph.add_node("political_risk", political_node)
    graph.add_node("infrastructure", infrastructure_node)
    graph.add_node("environment", environment_node)
    graph.add_node("financeability", financeability_node)
    graph.add_node("economist", economist_node)
    graph.add_node("redteam", redteam_node)
    graph.add_node("chair", chair_node)

    for section_agent in (
        "geoscience", "fiscal", "political_risk", "infrastructure",
        "environment", "financeability",
    ):
        graph.add_edge(START, section_agent)
        graph.add_edge(section_agent, "economist")
    graph.add_edge("economist", "redteam")
    graph.add_edge("redteam", "chair")
    graph.add_edge("chair", END)
    return graph.compile()


def run_committee(
    ctx: SnapshotContext, request: BlockRequest, narrator: Narrator
) -> tuple[Memo, dict]:
    app = build_graph(ctx, narrator)
    final = app.invoke(
        {"request": request, "sections": [], "tool_payloads": {}, "memo": None}
    )
    return final["memo"], final["tool_payloads"]
