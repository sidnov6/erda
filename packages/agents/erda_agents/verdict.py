"""Deterministic verdict rules (spec §10.6): the LLM words it, rules decide it.

Thresholds (stated constants, tested; the memo prints them):
- NO_GO   if sanctions_flag, or WDPA overlap > 25%, or EMV ≤ 0
- CONDITIONAL if EMV > 0 but P(EMV>0) < 0.6, or WDPA overlap > 10%
- GO      otherwise
"""

from __future__ import annotations

from erda_agents.memo_schema import VerdictBasis

WDPA_NO_GO_PCT = 25.0
WDPA_CONDITIONAL_PCT = 10.0
P_POSITIVE_CONDITIONAL = 0.6

GO, CONDITIONAL, NO_GO = "GO", "CONDITIONAL", "NO_GO"


def decide(basis: VerdictBasis) -> str:
    if basis.sanctions_flag:
        return NO_GO
    if basis.wdpa_overlap_pct > WDPA_NO_GO_PCT:
        return NO_GO
    if basis.emv_musd <= 0.0:
        return NO_GO
    if basis.p_emv_positive < P_POSITIVE_CONDITIONAL:
        return CONDITIONAL
    if basis.wdpa_overlap_pct > WDPA_CONDITIONAL_PCT:
        return CONDITIONAL
    return GO
