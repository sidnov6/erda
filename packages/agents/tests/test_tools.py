"""Tool tests on a SYNTHETIC mini-snapshot (spec §11.3) — fully offline."""

import pytest

from erda_agents.tools import economics, geoscience, screening
from erda_agents.tools.base import ToolDataMissing


def test_model_score_is_honest(ctx):
    out = geoscience.get_model_score(ctx, 60.0, 2.0)
    assert "NO MODEL" in out["model_status"]
    assert out["pg_source"] == "user-supplied"
    assert out["in_scoreable_mask"] is True
    assert out["source_ids"]


def test_offset_wells_and_basin_stats(ctx):
    out = geoscience.get_offset_wells(ctx, 60.0, 2.0, radius_km=50.0)
    assert out["n_wells"] == 3
    assert out["n_discoveries"] == 2
    assert out["nearest_wells"][0]["distance_km"] == 0.0
    assert "labels_harmonized" in out["source_ids"]

    basin = geoscience.get_basin_stats(ctx, 60.0, 2.0)
    assert basin["province_name"] == "Test Basin"
    assert basin["n_wildcats"] == 3
    assert basin["success_rate"] == pytest.approx(2 / 3, abs=1e-3)


def test_dev_concept_uses_stack_depth_and_costs(ctx):
    out = economics.classify_dev_concept(ctx, 60.0, 2.0, host_distance_km=30.0)
    assert out["water_depth_m"] == pytest.approx(350.0)
    assert out["concept"] == "shelf_tieback"
    assert out["cost_benchmarks"]["capex_usd_boe_low"] == "8"
    assert "curated_costs" in out["source_ids"]


def test_fiscal_governance_sanctions_financing(ctx):
    fis = screening.get_fiscal_regime(ctx, "TST")
    assert fis["cit_rate"] == 0.3
    with pytest.raises(ToolDataMissing, match="fiscal"):
        screening.get_fiscal_regime(ctx, "XXX")

    gov = screening.get_governance(ctx, "TST")
    assert gov["wgi_estimates"]["RL.EST"] == pytest.approx(1.2)
    assert gov["fsi_total"] is None  # FSI table absent → stated, not invented

    assert screening.screen_sanctions(ctx, "BAD", "Badland")["sanctioned"] is True
    clean = screening.screen_sanctions(ctx, "TST", "Testland")
    assert clean["sanctioned"] is False and clean["programs"] == []

    fin = screening.screen_financing(ctx)
    assert fin["n_restricting_upstream"] == 1


def test_run_economics_matches_engine_and_carries_provenance(ctx):
    out = economics.run_economics(
        pg=0.25,
        pg_provenance="user-supplied (§9.8)",
        resource_p90_p50_p10=(60.0, 100.0, 160.0),
        price_usd_bbl=70.0,
        price_provenance="curve M1 flat-real (yf_curve)",
        royalty_rate=0.10,
        cit_rate=0.30,
        fiscal_source_id="curated_fiscal",
        opex_usd_bbl=12.0,
        well_cost_musd=80.0,
        dev_capex_musd=500.0,
        cost_source_id="curated_costs",
        n_draws=200,
        seed=7,
    )
    assert out["emv_musd"] > 0
    assert out["mc"]["seed"] == 7
    assert out["pg_provenance"].startswith("user-supplied")
    assert set(out["source_ids"]) == {"erda_engine", "curated_fiscal", "curated_costs"}
    # deterministic: same inputs, same numbers
    again = economics.run_economics(
        pg=0.25,
        pg_provenance="user-supplied (§9.8)",
        resource_p90_p50_p10=(60.0, 100.0, 160.0),
        price_usd_bbl=70.0,
        price_provenance="curve M1 flat-real (yf_curve)",
        royalty_rate=0.10,
        cit_rate=0.30,
        fiscal_source_id="curated_fiscal",
        opex_usd_bbl=12.0,
        well_cost_musd=80.0,
        dev_capex_musd=500.0,
        cost_source_id="curated_costs",
        n_draws=200,
        seed=7,
    )
    assert out == again


def test_wdpa_absent_raises(ctx):
    with pytest.raises(ToolDataMissing, match="wdpa"):
        screening.get_protected_overlap(ctx, 60.0, 2.0)
