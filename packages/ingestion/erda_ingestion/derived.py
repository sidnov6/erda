"""Derived metrics engine (spec §4): pure functions, unit-tested, no I/O.

Every formula here is exercised by a hand-computed fixture in
tests/test_derived.py — the UI never renders a derived number whose formula
isn't pinned by a test (§8 validators). The Discovery-Monitor series lives in
Phase 2 with the label DB; it does not belong here.
"""

from __future__ import annotations

import pandas as pd

GALLONS_PER_BBL = 42


def crack_spread_321(rbob_usd_gal: float, ho_usd_gal: float, wti_usd_bbl: float) -> float:
    """3-2-1 crack spread, $/bbl: (2·RBOB·42 + 1·HO·42 − 3·WTI) / 3."""
    return (
        2 * rbob_usd_gal * GALLONS_PER_BBL + ho_usd_gal * GALLONS_PER_BBL - 3 * wti_usd_bbl
    ) / 3


def brent_wti_spread(brent_usd_bbl: float, wti_usd_bbl: float) -> float:
    """Brent − WTI, $/bbl."""
    return brent_usd_bbl - wti_usd_bbl


def prompt_spread(m1_usd_bbl: float, m2_usd_bbl: float) -> float:
    """M1 − M2, $/bbl. Positive → backwardation at the prompt."""
    return m1_usd_bbl - m2_usd_bbl


def curve_slope_m1_m12(m1_usd_bbl: float, m12_usd_bbl: float) -> float:
    """M1 − M12, $/bbl. Positive → backwardation; negative → contango."""
    return m1_usd_bbl - m12_usd_bbl


def curve_structure(m1_usd_bbl: float, m12_usd_bbl: float) -> str:
    slope = curve_slope_m1_m12(m1_usd_bbl, m12_usd_bbl)
    if slope > 0:
        return "backwardation"
    if slope < 0:
        return "contango"
    return "flat"


def days_of_forward_cover(stocks_kbbl: float, consumption_kbd: float) -> float:
    """Days of forward cover: stocks (kbbl) ÷ consumption rate (kb/d)."""
    if consumption_kbd <= 0:
        raise ValueError("consumption must be positive")
    return stocks_kbbl / consumption_kbd


def opec_compliance_pct(pledged_cut_kbd: float, delivered_cut_kbd: float) -> float:
    """Delivered cut ÷ pledged cut, %. >100 means over-compliance."""
    if pledged_cut_kbd <= 0:
        raise ValueError("pledged cut must be positive")
    return 100.0 * delivered_cut_kbd / pledged_cut_kbd


def wow_stock_change(this_week_kbbl: float, last_week_kbbl: float) -> float:
    """Week-over-week build (+) / draw (−), kbbl — WPSR internal-consistency input."""
    return this_week_kbbl - last_week_kbbl


def five_year_band(weekly: pd.Series, asof: pd.Timestamp) -> pd.DataFrame:
    """Per week-of-year min/max over the five calendar years before ``asof``'s year.

    Input: weekly series with a DatetimeIndex. Output: [week_of_year, band_min,
    band_max] for the INV panel's 5-yr range band (§8 panel 4). Weeks with no
    history in the window are simply absent — never interpolated.
    """
    start_year = asof.year - 5
    window = weekly[
        (weekly.index.year >= start_year) & (weekly.index.year < asof.year)
    ]
    if window.empty:
        return pd.DataFrame(columns=["week_of_year", "band_min", "band_max"])
    grouped = window.groupby(window.index.isocalendar().week.astype(int))
    out = grouped.agg(band_min="min", band_max="max").reset_index()
    return out.rename(columns={"week": "week_of_year"})


def rigs_production_lead_lag(
    rigs: pd.Series, production: pd.Series, max_lag_months: int = 12
) -> pd.DataFrame:
    """Correlation of rig count vs production at rig-leads-production lags 0..N.

    Both series must share a monthly DatetimeIndex. Computed, not asserted (§4):
    the panel renders whatever the data says.
    """
    if not rigs.index.equals(production.index):
        raise ValueError("rigs and production must share the same index")
    rows = []
    for lag in range(max_lag_months + 1):
        corr = rigs.shift(lag).corr(production)
        rows.append({"lag_months": lag, "correlation": corr})
    return pd.DataFrame(rows)
