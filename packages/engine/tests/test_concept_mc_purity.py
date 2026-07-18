"""Dev-concept classifier boundaries (§10.4), seeded Monte Carlo semantics
(§10.5), and the import-purity guard (P4 gate: engine is import-pure, no I/O)."""

from pathlib import Path

import pytest

from erda_engine import concept, dcf, monte_carlo

ENGINE_SRC = Path(__file__).parents[1] / "erda_engine"


def test_concept_boundaries_exact():
    # water depth ≤ 0 → onshore · ≤400 m & host ≤50 km → shelf tieback ·
    # >400 m & host ≤70 km → deepwater tieback · else FPSO standalone
    assert concept.classify(water_depth_m=0.0, host_distance_km=999.0) == "onshore"
    assert concept.classify(water_depth_m=-0.0, host_distance_km=1.0) == "onshore"
    assert concept.classify(water_depth_m=400.0, host_distance_km=50.0) == "shelf_tieback"
    assert concept.classify(water_depth_m=400.0, host_distance_km=50.1) == "fpso_standalone"
    assert concept.classify(water_depth_m=400.1, host_distance_km=70.0) == "deepwater_tieback"
    assert concept.classify(water_depth_m=400.1, host_distance_km=70.1) == "fpso_standalone"
    assert concept.classify(water_depth_m=2000.0, host_distance_km=300.0) == "fpso_standalone"
    with pytest.raises(ValueError, match="nan"):
        concept.classify(water_depth_m=float("nan"), host_distance_km=1.0)


BASE = dict(
    production_profile=[0.2, 0.2, 0.2, 0.2, 0.2],
    schedule_years=2,
    royalty_rate=0.10,
    cit_rate=0.30,
    opex_usd_bbl=12.0,
    well_cost_musd=80.0,
    capex_schedule=[0.0, 1.0],
    discount_rate=0.10,
)


def test_monte_carlo_reproducible_and_degenerate_case_collapses():
    mc_a = monte_carlo.run_emv(
        pg=0.25,
        resource_p90_p50_p10=(60.0, 100.0, 160.0),
        price_usd_bbl=70.0,
        price_sigma=0.2,
        dev_capex_musd=500.0,
        capex_spread=0.3,
        n_draws=2_000,
        seed=42,
        **BASE,
    )
    mc_b = monte_carlo.run_emv(
        pg=0.25,
        resource_p90_p50_p10=(60.0, 100.0, 160.0),
        price_usd_bbl=70.0,
        price_sigma=0.2,
        dev_capex_musd=500.0,
        capex_spread=0.3,
        n_draws=2_000,
        seed=42,
        **BASE,
    )
    assert mc_a.emv_mean_musd == mc_b.emv_mean_musd  # bit-identical, same seed
    assert 0.0 <= mc_a.p_emv_positive <= 1.0
    assert mc_a.emv_p10_musd <= mc_a.emv_p50_musd <= mc_a.emv_p90_musd

    # degenerate distributions (no spread anywhere) collapse to the
    # deterministic EMV for every draw
    det_npv = dcf.evaluate_block(
        resource_mmbbl=100.0, price_usd_bbl=70.0, dev_capex_musd=500.0, **BASE
    ).npv_musd
    from erda_engine import emv as emv_mod

    det_emv = emv_mod.expected_monetary_value(0.25, det_npv, 80.0)
    mc_c = monte_carlo.run_emv(
        pg=0.25,
        resource_p90_p50_p10=(100.0, 100.0, 100.0),
        price_usd_bbl=70.0,
        price_sigma=0.0,
        dev_capex_musd=500.0,
        capex_spread=0.0,
        n_draws=500,
        seed=1,
        **BASE,
    )
    assert mc_c.emv_mean_musd == pytest.approx(det_emv, abs=1e-6)
    assert mc_c.emv_p10_musd == pytest.approx(mc_c.emv_p90_musd, abs=1e-6)


def test_monte_carlo_pg_monotonicity():
    kwargs = dict(
        resource_p90_p50_p10=(60.0, 100.0, 160.0),
        price_usd_bbl=70.0,
        price_sigma=0.2,
        dev_capex_musd=500.0,
        capex_spread=0.3,
        n_draws=2_000,
        seed=7,
        **BASE,
    )
    lo = monte_carlo.run_emv(pg=0.1, **kwargs)
    hi = monte_carlo.run_emv(pg=0.5, **kwargs)
    assert hi.emv_mean_musd > lo.emv_mean_musd
    assert hi.p_emv_positive >= lo.p_emv_positive


FORBIDDEN = ["import httpx", "import requests", "import urllib", "import socket",
             "open(", "Path(", "read_", "to_parquet", "import pandas"]


def test_engine_is_import_pure():
    """P4 gate: no I/O, no network, no pandas in the deterministic core."""
    for src in sorted(ENGINE_SRC.glob("*.py")):
        text = src.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{src.name} contains forbidden {token!r}"
