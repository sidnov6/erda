"""Fiscal application (spec §10.5) — tax/royalty regime, screening level.

DETERMINISTIC CORE: pure functions over floats. Conventions (also stated in
tests/fixtures/golden_block.yaml):
- royalty on gross revenue;
- corporate income tax on (revenue − royalty − opex − depreciation), with
  straight-line depreciation of development capex over the production years;
- negative taxable income → zero tax, no refund, no loss carryforward
  (screening simplification, stated in every memo that uses this engine).
PSC regimes are a curated-input translation into equivalent take terms and
arrive with Phase 5 wiring; the engine's fiscal core stays this explicit.
"""

from __future__ import annotations


def royalty(revenue_musd: float, royalty_rate: float) -> float:
    if not 0.0 <= royalty_rate < 1.0:
        raise ValueError(f"royalty_rate out of [0,1): {royalty_rate}")
    return revenue_musd * royalty_rate


def corporate_tax(
    revenue_musd: float,
    royalty_musd: float,
    opex_musd: float,
    depreciation_musd: float,
    cit_rate: float,
) -> float:
    if not 0.0 <= cit_rate < 1.0:
        raise ValueError(f"cit_rate out of [0,1): {cit_rate}")
    taxable = revenue_musd - royalty_musd - opex_musd - depreciation_musd
    return max(0.0, taxable * cit_rate)
