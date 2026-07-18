"""Property tests (spec §10.5): the monotonicities that must hold, plus fiscal
edge semantics (negative taxable income → zero tax, never a refund)."""

import pytest

from erda_engine import dcf, emv

BASE = dict(
    resource_mmbbl=100.0,
    production_profile=[0.2, 0.2, 0.2, 0.2, 0.2],
    schedule_years=2,
    price_usd_bbl=70.0,
    royalty_rate=0.10,
    cit_rate=0.30,
    opex_usd_bbl=12.0,
    well_cost_musd=80.0,
    dev_capex_musd=500.0,
    capex_schedule=[0.0, 1.0],
    discount_rate=0.10,
)


def _npv(**overrides) -> float:
    return dcf.evaluate_block(**{**BASE, **overrides}).npv_musd


def test_price_up_npv_up():
    npvs = [_npv(price_usd_bbl=p) for p in (40.0, 55.0, 70.0, 85.0, 100.0)]
    assert all(a < b for a, b in zip(npvs, npvs[1:], strict=False))


def test_royalty_up_take_up_and_npv_down():
    takes, npvs = [], []
    for roy in (0.0, 0.05, 0.10, 0.20, 0.30):
        case = dcf.evaluate_block(**{**BASE, "royalty_rate": roy})
        takes.append(case.government_take)
        npvs.append(case.npv_musd)
    assert all(a < b for a, b in zip(takes, takes[1:], strict=False))
    assert all(a > b for a, b in zip(npvs, npvs[1:], strict=False))


def test_pg_up_emv_up():
    npv = _npv()
    emvs = [
        emv.expected_monetary_value(pg=pg, npv_success_musd=npv, well_cost_musd=80.0)
        for pg in (0.05, 0.15, 0.25, 0.5, 0.9)
    ]
    assert all(a < b for a, b in zip(emvs, emvs[1:], strict=False))


def test_emv_formula_exact():
    # EMV = Pg·NPV − (1−Pg)·well_cost, nothing more
    assert emv.expected_monetary_value(
        pg=0.3, npv_success_musd=1000.0, well_cost_musd=100.0
    ) == pytest.approx(0.3 * 1000.0 - 0.7 * 100.0)


def test_negative_taxable_income_yields_zero_tax_not_refund():
    # price low enough that revenue < royalty+opex+depreciation in every year
    case = dcf.evaluate_block(**{**BASE, "price_usd_bbl": 15.0})
    assert all(t >= 0.0 for t in case.tax_musd)
    assert case.npv_musd < 0


def test_breakeven_is_a_fixed_point():
    case = dcf.evaluate_block(**BASE)
    at_breakeven = _npv(price_usd_bbl=case.breakeven_usd_bbl)
    assert at_breakeven == pytest.approx(0.0, abs=1e-3)


def test_payback_none_when_never_recovered():
    case = dcf.evaluate_block(**{**BASE, "price_usd_bbl": 15.0})
    assert case.payback_year is None


def test_profile_must_sum_to_one_and_inputs_validated():
    with pytest.raises(ValueError, match="profile"):
        dcf.evaluate_block(**{**BASE, "production_profile": [0.5, 0.4]})
    with pytest.raises(ValueError, match="capex_schedule"):
        dcf.evaluate_block(**{**BASE, "capex_schedule": [0.9]})
    with pytest.raises(ValueError, match="pg"):
        emv.expected_monetary_value(pg=1.5, npv_success_musd=1.0, well_cost_musd=1.0)
