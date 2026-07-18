"""Expected monetary value (spec §10.5) — the industry's decision metric.

EMV = Pg · NPV(success) − (1 − Pg) · dry-hole cost

NPV(success) includes the exploration well cost inside its own cash flows
(year 0); the dry branch pays only the well. Pg is USER-SUPPLIED while the
§9.8 falsification gate stands — every memo states that provenance.
DETERMINISTIC CORE — pure arithmetic.
"""

from __future__ import annotations


def expected_monetary_value(
    pg: float, npv_success_musd: float, well_cost_musd: float
) -> float:
    if not 0.0 <= pg <= 1.0:
        raise ValueError(f"pg out of [0,1]: {pg}")
    if well_cost_musd < 0:
        raise ValueError(f"well cost must be non-negative: {well_cost_musd}")
    return pg * npv_success_musd - (1.0 - pg) * well_cost_musd
