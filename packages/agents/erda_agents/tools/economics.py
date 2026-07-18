"""Economist + Infrastructure tools (§10.2): dev-concept classification and the
engine runner — the ONLY path to money numbers (§0 rule 3)."""

from __future__ import annotations

import csv

import numpy as np

from erda_agents.tools.base import SnapshotContext, ToolDataMissing
from erda_engine import concept as concept_mod
from erda_engine import dcf, emv, monte_carlo


def classify_dev_concept(
    ctx: SnapshotContext, lat: float, lon: float, host_distance_km: float
) -> dict:
    """§10.4: water depth from the stack bathymetry; host distance supplied by
    the Infrastructure agent's data (GEM-derived when available, else stated)."""
    spec = ctx.grid_spec
    row, col = spec.latlon_to_rowcol(np.array([lat]), np.array([lon]))
    elevation = float(ctx.stack["elevation_m"].values[row[0], col[0]])
    water_depth_m = max(0.0, -elevation)
    concept = concept_mod.classify(water_depth_m=water_depth_m, host_distance_km=host_distance_km)

    costs_path = ctx.curated / "cost_benchmarks.csv"
    if not costs_path.exists():
        raise ToolDataMissing("curated cost_benchmarks.csv missing")
    with costs_path.open(encoding="utf-8") as fh:
        rows = {r["concept"]: r for r in csv.DictReader(fh)}
    if concept not in rows:
        raise ToolDataMissing(f"no cost benchmark row for concept {concept!r}")
    row_c = rows[concept]
    return {
        "water_depth_m": round(water_depth_m, 1),
        "host_distance_km": host_distance_km,
        "concept": concept,
        "cost_benchmarks": {
            k: (row_c[k] if row_c[k] != "" else None)
            for k in row_c
            if k not in ("source_url", "retrieved_at", "notes")
        },
        "cost_notes": row_c.get("notes", ""),
        "source_ids": ["etopo2022", "curated_costs", "erda_engine.concept"],
    }


def run_economics(
    *,
    pg: float,
    pg_provenance: str,
    resource_p90_p50_p10: tuple[float, float, float],
    price_usd_bbl: float,
    price_provenance: str,
    royalty_rate: float,
    cit_rate: float,
    fiscal_source_id: str,
    opex_usd_bbl: float,
    well_cost_musd: float,
    dev_capex_musd: float,
    cost_source_id: str,
    production_profile: list[float] | None = None,
    schedule_years: int = 3,
    capex_schedule: list[float] | None = None,
    discount_rate: float = 0.10,
    n_draws: int = 10_000,
    seed: int = 7,
) -> dict:
    """Deterministic engine invocation. Every argument's provenance is passed in
    and travels out on the result — the agent assembles, the engine computes."""
    profile = production_profile or [0.15, 0.15, 0.12, 0.11, 0.10, 0.09, 0.08, 0.07, 0.07, 0.06]
    cap_sched = capex_schedule or [0.4, 0.6, 0.0][: schedule_years] + [0.0] * max(
        0, schedule_years - 3
    )
    # normalize capex schedule defensively (engine validates the sum)
    total = sum(cap_sched)
    cap_sched = [c / total for c in cap_sched] if total > 0 else [1.0] + [0.0] * (
        schedule_years - 1
    )

    block = dcf.evaluate_block(
        resource_mmbbl=resource_p90_p50_p10[1],
        production_profile=profile,
        schedule_years=schedule_years,
        price_usd_bbl=price_usd_bbl,
        royalty_rate=royalty_rate,
        cit_rate=cit_rate,
        opex_usd_bbl=opex_usd_bbl,
        well_cost_musd=well_cost_musd,
        dev_capex_musd=dev_capex_musd,
        capex_schedule=cap_sched,
        discount_rate=discount_rate,
    )
    emv_det = emv.expected_monetary_value(pg, block.npv_musd, well_cost_musd)
    mc = monte_carlo.run_emv(
        pg=pg,
        resource_p90_p50_p10=resource_p90_p50_p10,
        price_usd_bbl=price_usd_bbl,
        price_sigma=0.25,
        dev_capex_musd=dev_capex_musd,
        capex_spread=0.30,
        n_draws=n_draws,
        seed=seed,
        production_profile=profile,
        schedule_years=schedule_years,
        royalty_rate=royalty_rate,
        cit_rate=cit_rate,
        opex_usd_bbl=opex_usd_bbl,
        well_cost_musd=well_cost_musd,
        capex_schedule=cap_sched,
        discount_rate=discount_rate,
    )
    return {
        "pg": pg,
        "pg_provenance": pg_provenance,
        "npv_success_musd": round(block.npv_musd, 2),
        "emv_musd": round(emv_det, 2),
        "breakeven_usd_bbl": round(block.breakeven_usd_bbl, 2),
        "government_take": round(block.government_take, 4),
        "payback_year": block.payback_year,
        "mc": {
            "emv_mean_musd": round(mc.emv_mean_musd, 2),
            "emv_p10_musd": round(mc.emv_p10_musd, 2),
            "emv_p50_musd": round(mc.emv_p50_musd, 2),
            "emv_p90_musd": round(mc.emv_p90_musd, 2),
            "p_emv_positive": round(mc.p_emv_positive, 4),
            "n_draws": mc.n_draws,
            "seed": mc.seed,
        },
        "assumptions": {
            "price_sigma": 0.25,
            "capex_spread": 0.30,
            "discount_rate": discount_rate,
            "price_provenance": price_provenance,
            "fiscal_model_note": "royalty + CIT with straight-line depreciation; "
            "no loss carryforward (screening simplification)",
        },
        "source_ids": ["erda_engine", fiscal_source_id, cost_source_id],
    }
