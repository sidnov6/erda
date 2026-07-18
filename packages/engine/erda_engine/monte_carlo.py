"""Seeded Monte Carlo over resource × price × capex (spec §10.5).

DETERMINISTIC CORE: numpy Generator seeded by the caller — same seed, same
inputs, bit-identical outputs (the memo determinism check depends on it).

Distributions (stated, not hidden):
- resource: lognormal parameterized by (P90, P50, P10) — median = P50,
  sigma = ln(P10/P50) / z90 with z90 = 1.2815516 (and the P90 must mirror:
  asymmetric triples are rejected rather than silently averaged);
- price: lognormal, median = deck price, sigma = `price_sigma` (0 → constant);
- capex: uniform on ±`capex_spread` × dev capex.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from erda_engine import dcf, emv

_Z90 = 1.2815515655446004
_SYMMETRY_TOL = 0.05  # relative tolerance on P90·P10 = P50² (lognormal symmetry)


@dataclass(frozen=True)
class MonteCarloResult:
    emv_mean_musd: float
    emv_p10_musd: float
    emv_p50_musd: float
    emv_p90_musd: float
    p_emv_positive: float
    n_draws: int
    seed: int


def _resource_sigma(p90: float, p50: float, p10: float) -> float:
    if not 0 < p90 <= p50 <= p10:
        raise ValueError(f"resource triple must satisfy 0 < P90 ≤ P50 ≤ P10: {(p90, p50, p10)}")
    if p90 == p50 == p10:
        return 0.0
    geometric_mid = (p90 * p10) / (p50 * p50)
    if abs(geometric_mid - 1.0) > _SYMMETRY_TOL:
        raise ValueError(
            f"resource triple is not lognormal-consistent (P90·P10 ≠ P50²): {(p90, p50, p10)}"
        )
    return float(np.log(p10 / p50) / _Z90)


def run_emv(
    *,
    pg: float,
    resource_p90_p50_p10: tuple[float, float, float],
    price_usd_bbl: float,
    price_sigma: float,
    dev_capex_musd: float,
    capex_spread: float,
    n_draws: int,
    seed: int,
    production_profile: list[float],
    schedule_years: int,
    royalty_rate: float,
    cit_rate: float,
    opex_usd_bbl: float,
    well_cost_musd: float,
    capex_schedule: list[float],
    discount_rate: float,
) -> MonteCarloResult:
    if n_draws < 1:
        raise ValueError("n_draws must be ≥ 1")
    if not 0.0 <= capex_spread < 1.0:
        raise ValueError(f"capex_spread out of [0,1): {capex_spread}")
    p90, p50, p10 = resource_p90_p50_p10
    sigma_r = _resource_sigma(p90, p50, p10)

    rng = np.random.default_rng(seed)
    if sigma_r > 0:
        resources = p50 * np.exp(sigma_r * rng.standard_normal(n_draws))
    else:
        resources = np.full(n_draws, p50)
    prices = (
        price_usd_bbl * np.exp(price_sigma * rng.standard_normal(n_draws))
        if price_sigma > 0
        else np.full(n_draws, price_usd_bbl)
    )
    capexes = dev_capex_musd * (1.0 + capex_spread * rng.uniform(-1.0, 1.0, n_draws))

    emvs = np.empty(n_draws)
    for i in range(n_draws):
        block = dcf.evaluate_block(
            resource_mmbbl=float(resources[i]),
            production_profile=production_profile,
            schedule_years=schedule_years,
            price_usd_bbl=float(prices[i]),
            royalty_rate=royalty_rate,
            cit_rate=cit_rate,
            opex_usd_bbl=opex_usd_bbl,
            well_cost_musd=well_cost_musd,
            dev_capex_musd=float(capexes[i]),
            capex_schedule=capex_schedule,
            discount_rate=discount_rate,
            light=True,
        )
        emvs[i] = emv.expected_monetary_value(pg, block.npv_musd, well_cost_musd)

    p10_emv, p50_emv, p90_emv = np.percentile(emvs, [10.0, 50.0, 90.0])
    return MonteCarloResult(
        emv_mean_musd=float(emvs.mean()),
        emv_p10_musd=float(p10_emv),
        emv_p50_musd=float(p50_emv),
        emv_p90_musd=float(p90_emv),
        p_emv_positive=float((emvs > 0).mean()),
        n_draws=n_draws,
        seed=seed,
    )
