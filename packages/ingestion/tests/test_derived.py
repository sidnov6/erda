"""Hand-computed fixtures for every derived-metric formula (spec §8).

Worked arithmetic lives in the comments so a reviewer can check by hand.
"""

import math

import pandas as pd
import pytest

from erda_ingestion import derived


def test_crack_spread_321():
    # 2·(2.50·42) = 210.0 ; 1·(2.60·42) = 109.2 ; 3·70 = 210.0
    # (210.0 + 109.2 − 210.0) / 3 = 109.2 / 3 = 36.4
    assert derived.crack_spread_321(2.50, 2.60, 70.0) == pytest.approx(36.4)


def test_brent_wti_spread():
    # 74.12 − 70.05 = 4.07
    assert derived.brent_wti_spread(74.12, 70.05) == pytest.approx(4.07)


def test_prompt_spread_and_structure():
    # backwardated prompt: 80.00 − 79.40 = 0.60
    assert derived.prompt_spread(80.00, 79.40) == pytest.approx(0.60)
    # M1 82.00, M12 78.50 → slope +3.50 → backwardation
    assert derived.curve_slope_m1_m12(82.00, 78.50) == pytest.approx(3.50)
    assert derived.curve_structure(82.00, 78.50) == "backwardation"
    # M1 70.00, M12 73.25 → slope −3.25 → contango
    assert derived.curve_structure(70.00, 73.25) == "contango"
    assert derived.curve_structure(70.0, 70.0) == "flat"


def test_days_of_forward_cover():
    # 421,000 kbbl ÷ 20,000 kb/d = 21.05 days
    assert derived.days_of_forward_cover(421_000, 20_000) == pytest.approx(21.05)
    with pytest.raises(ValueError):
        derived.days_of_forward_cover(1.0, 0.0)


def test_opec_compliance_pct():
    # delivered 450 of pledged 500 kb/d → 90%
    assert derived.opec_compliance_pct(500, 450) == pytest.approx(90.0)
    # over-compliance: 550/500 → 110%
    assert derived.opec_compliance_pct(500, 550) == pytest.approx(110.0)
    with pytest.raises(ValueError):
        derived.opec_compliance_pct(0, 100)


def test_wow_stock_change():
    # build: 425,300 − 421,000 = +4,300
    assert derived.wow_stock_change(425_300, 421_000) == pytest.approx(4_300)
    # draw: 421,000 − 425,300 = −4,300
    assert derived.wow_stock_change(421_000, 425_300) == pytest.approx(-4_300)


def test_rigs_production_lead_lag_perfect_lead():
    # production copies rigs shifted 3 months later → correlation peaks at lag 3
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    rigs = pd.Series(range(24), index=idx, dtype=float)
    production = rigs.shift(3)
    out = derived.rigs_production_lead_lag(rigs, production, max_lag_months=6)
    assert list(out["lag_months"]) == list(range(7))
    assert out.loc[out["lag_months"] == 3, "correlation"].iloc[0] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        derived.rigs_production_lead_lag(rigs, production.reset_index(drop=True))


def test_lead_lag_correlation_is_nan_safe():
    idx = pd.date_range("2020-01-01", periods=5, freq="MS")
    rigs = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx)
    production = pd.Series([float("nan")] * 5, index=idx)
    out = derived.rigs_production_lead_lag(rigs, production, max_lag_months=2)
    assert math.isnan(out["correlation"].iloc[0])
