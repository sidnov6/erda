"""Golden-case tests (spec §11.3): the engine must reproduce the hand-computed
fixture. The test loads the YAML and passes plain values in — the engine itself
never touches a file (import purity)."""

from pathlib import Path

import pytest
import yaml

from erda_engine import dcf, emv

FIXTURE = Path(__file__).parents[3] / "tests" / "fixtures" / "golden_block.yaml"


@pytest.fixture(scope="module")
def golden() -> dict:
    return yaml.safe_load(FIXTURE.read_text())


@pytest.fixture(scope="module")
def case(golden: dict) -> dcf.BlockEconomics:
    i = golden["inputs"]
    return dcf.evaluate_block(
        resource_mmbbl=i["resource_mmbbl"],
        production_profile=i["production_profile"],
        schedule_years=i["schedule_years"],
        price_usd_bbl=i["price_usd_bbl"],
        royalty_rate=i["royalty_rate"],
        cit_rate=i["cit_rate"],
        opex_usd_bbl=i["opex_usd_bbl"],
        well_cost_musd=i["well_cost_musd"],
        dev_capex_musd=i["dev_capex_musd"],
        capex_schedule=i["capex_schedule"],
        discount_rate=i["discount_rate"],
    )


def test_golden_intermediates(golden: dict, case: dcf.BlockEconomics):
    e = golden["expected"]
    tol = e["tolerance"]
    # first production year (index = schedule_years)
    y = golden["inputs"]["schedule_years"]
    assert case.production_mmbbl[y] == pytest.approx(e["annual_production_mmbbl"], abs=tol)
    assert case.revenue_musd[y] == pytest.approx(e["annual_revenue_musd"], abs=tol)
    assert case.royalty_musd[y] == pytest.approx(e["annual_royalty_musd"], abs=tol)
    assert case.opex_musd[y] == pytest.approx(e["annual_opex_musd"], abs=tol)
    assert case.tax_musd[y] == pytest.approx(e["annual_tax_musd"], abs=tol)
    assert case.ncf_musd[y] == pytest.approx(e["annual_ncf_musd"], abs=tol)


def test_golden_npv_take_payback_breakeven(golden: dict, case: dcf.BlockEconomics):
    e = golden["expected"]
    assert case.npv_musd == pytest.approx(e["npv_success_musd"], abs=e["tolerance"])
    assert case.government_take == pytest.approx(
        e["government_take"], abs=e["tolerance_ratio"]
    )
    assert case.payback_year == e["payback_year"]
    assert case.breakeven_usd_bbl == pytest.approx(
        e["breakeven_usd_bbl"], abs=e["tolerance_price"]
    )


def test_golden_emv(golden: dict, case: dcf.BlockEconomics):
    e = golden["expected"]
    i = golden["inputs"]
    result = emv.expected_monetary_value(
        pg=i["pg"], npv_success_musd=case.npv_musd, well_cost_musd=i["well_cost_musd"]
    )
    assert result == pytest.approx(e["emv_musd"], abs=e["tolerance"])
