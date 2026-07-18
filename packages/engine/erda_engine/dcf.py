"""Discounted cash flow (spec §10.5). DETERMINISTIC CORE — pure, no I/O.

Model (golden fixture documents the hand math):
- year 0: exploration well cost (the success branch pays it; §10.5's EMV then
  charges the dry branch (1−Pg)·well_cost);
- development capex per `capex_schedule` fractions over the pre-production
  years; production starts at year `schedule_years`, produced volumes =
  `resource_mmbbl × production_profile[i]`;
- flat real price; discounting to year 0 at `discount_rate`;
- fiscal per erda_engine.fiscal (royalty + CIT with straight-line depreciation
  over the production years, no negative tax);
- government take = PV(royalty + tax) / PV(revenue − opex − capex − well);
- payback = first year cumulative undiscounted NCF ≥ 0, else None;
- breakeven = price where NPV = 0, found by deterministic bisection.
"""

from __future__ import annotations

from dataclasses import dataclass

from erda_engine import fiscal

_PROFILE_TOL = 1e-9


@dataclass(frozen=True)
class BlockEconomics:
    npv_musd: float
    government_take: float
    payback_year: int | None
    breakeven_usd_bbl: float
    production_mmbbl: list[float]
    revenue_musd: list[float]
    royalty_musd: list[float]
    opex_musd: list[float]
    tax_musd: list[float]
    capex_musd: list[float]
    ncf_musd: list[float]


def _validate(production_profile: list[float], capex_schedule: list[float]) -> None:
    if abs(sum(production_profile) - 1.0) > _PROFILE_TOL or any(
        f < 0 for f in production_profile
    ):
        raise ValueError(
            f"production profile must be non-negative and sum to 1: {production_profile}"
        )
    if abs(sum(capex_schedule) - 1.0) > _PROFILE_TOL or any(f < 0 for f in capex_schedule):
        raise ValueError(f"capex_schedule must be non-negative and sum to 1: {capex_schedule}")


def _cash_flows(
    resource_mmbbl: float,
    production_profile: list[float],
    schedule_years: int,
    price_usd_bbl: float,
    royalty_rate: float,
    cit_rate: float,
    opex_usd_bbl: float,
    well_cost_musd: float,
    dev_capex_musd: float,
    capex_schedule: list[float],
) -> tuple[
    list[float], list[float], list[float], list[float], list[float], list[float], list[float]
]:
    n_years = schedule_years + len(production_profile)
    production = [0.0] * n_years
    for i, frac in enumerate(production_profile):
        production[schedule_years + i] = resource_mmbbl * frac

    capex = [0.0] * n_years
    capex[0] += well_cost_musd
    for i, frac in enumerate(capex_schedule):
        capex[i] += dev_capex_musd * frac

    n_prod_years = len(production_profile)
    depreciation_per_year = dev_capex_musd / n_prod_years if n_prod_years else 0.0

    revenue, roy, opex, tax, ncf = [], [], [], [], []
    for t in range(n_years):
        rev_t = production[t] * price_usd_bbl
        roy_t = fiscal.royalty(rev_t, royalty_rate)
        opex_t = production[t] * opex_usd_bbl
        dep_t = depreciation_per_year if production[t] > 0 else 0.0
        tax_t = fiscal.corporate_tax(rev_t, roy_t, opex_t, dep_t, cit_rate)
        revenue.append(rev_t)
        roy.append(roy_t)
        opex.append(opex_t)
        tax.append(tax_t)
        ncf.append(rev_t - roy_t - opex_t - tax_t - capex[t])
    return production, revenue, roy, opex, tax, capex, ncf


def _npv(flows: list[float], discount_rate: float) -> float:
    return sum(f / (1.0 + discount_rate) ** t for t, f in enumerate(flows))


def evaluate_block(
    *,
    resource_mmbbl: float,
    production_profile: list[float],
    schedule_years: int,
    price_usd_bbl: float,
    royalty_rate: float,
    cit_rate: float,
    opex_usd_bbl: float,
    well_cost_musd: float,
    dev_capex_musd: float,
    capex_schedule: list[float],
    discount_rate: float,
    light: bool = False,
) -> BlockEconomics:
    """`light=True` skips the breakeven bisection (Monte Carlo hot path —
    identical NPV/take/payback, breakeven reported as NaN)."""
    _validate(production_profile, capex_schedule)
    if schedule_years < len(capex_schedule) - 1:
        raise ValueError("capex_schedule longer than the pre-production window")

    def flows_at(price: float):
        return _cash_flows(
            resource_mmbbl, production_profile, schedule_years, price, royalty_rate,
            cit_rate, opex_usd_bbl, well_cost_musd, dev_capex_musd, capex_schedule,
        )

    production, revenue, roy, opex, tax, capex, ncf = flows_at(price_usd_bbl)
    npv = _npv(ncf, discount_rate)

    pv_take = _npv([r + t for r, t in zip(roy, tax, strict=True)], discount_rate)
    pre_take = [
        rev - ox - cx for rev, ox, cx in zip(revenue, opex, capex, strict=True)
    ]
    pv_pre_take = _npv(pre_take, discount_rate)
    take = pv_take / pv_pre_take if pv_pre_take > 0 else float("nan")

    payback: int | None = None
    cumulative = 0.0
    for t, f in enumerate(ncf):
        cumulative += f
        if cumulative >= 0.0:
            payback = t
            break

    breakeven = (
        float("nan")
        if light
        else _bisect_breakeven(
            lambda p: _npv(flows_at(p)[6], discount_rate), lo=0.0, hi=max(price_usd_bbl, 1.0)
        )
    )

    return BlockEconomics(
        npv_musd=npv,
        government_take=take,
        payback_year=payback,
        breakeven_usd_bbl=breakeven,
        production_mmbbl=production,
        revenue_musd=revenue,
        royalty_musd=roy,
        opex_musd=opex,
        tax_musd=tax,
        capex_musd=capex,
        ncf_musd=ncf,
    )


def _bisect_breakeven(npv_of_price, lo: float, hi: float, tol: float = 1e-6) -> float:
    """Deterministic bisection for NPV(price) = 0. NPV is monotone-increasing in
    price; the bracket expands until it straddles zero (bounded)."""
    f_lo = npv_of_price(lo)
    if f_lo > 0:
        return lo  # profitable even at zero price — degenerate, but defined
    f_hi = npv_of_price(hi)
    expansions = 0
    while f_hi < 0 and expansions < 60:
        hi *= 2.0
        f_hi = npv_of_price(hi)
        expansions += 1
    if f_hi < 0:
        return float("inf")  # never profitable at any finite price
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = npv_of_price(mid)
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if f_mid < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
