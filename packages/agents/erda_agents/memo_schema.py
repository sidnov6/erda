"""Memo schema (spec §10.6) + tool law enforcement (§10.3).

Every quantitative field is a QuantField carrying `source_ids` — the schema
makes an uncited number unrepresentable rather than merely discouraged. The
LLM writes `narrative` strings only; it cannot mint numbers into the schema.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

MIN_CITATION_COVERAGE = 0.9


class QuantField(BaseModel):
    """A number (or categorical fact) with mandatory provenance."""

    value: float | int | str | bool
    unit: str | None = None
    source_ids: list[str] = Field(min_length=1)

    @field_validator("source_ids")
    @classmethod
    def _non_empty_ids(cls, v: list[str]) -> list[str]:
        if any(not s.strip() for s in v):
            raise ValueError("blank source_id")
        return v


class MemoSection(BaseModel):
    agent: str
    narrative: str = ""  # LLM prose — words, never the source of numbers
    quant: dict[str, QuantField] = {}


class VerdictBasis(BaseModel):
    """The deterministic inputs the verdict rules saw — auditable, replayable."""

    emv_musd: float
    p_emv_positive: float
    sanctions_flag: bool
    wdpa_overlap_pct: float
    pg: float
    pg_provenance: str  # e.g. "user-supplied (§9.8 — no model Pg ships)"


class Memo(BaseModel):
    block_id: str
    generated_at: str
    snapshot_note: str
    verdict: str  # GO | CONDITIONAL | NO_GO — set by rules, worded by the LLM
    verdict_basis: VerdictBasis
    sections: list[MemoSection]
    redteam_narrative: str  # required section: what would make this wrong
    citation_coverage: float
    quant_hash: str


def citation_coverage(sections: list[MemoSection]) -> float:
    """cited quant fields ÷ total quant fields (§10.3). Schema guarantees each
    QuantField has source_ids, so uncited fields can only appear as raw dict
    smuggling — counted against coverage here for defense in depth."""
    total = 0
    cited = 0
    for section in sections:
        for field in section.quant.values():
            total += 1
            if isinstance(field, QuantField) and field.source_ids:
                cited += 1
    return 1.0 if total == 0 else cited / total


def quant_hash(sections: list[MemoSection], verdict: str, basis: VerdictBasis) -> str:
    """The §11.3 determinism hash: canonical JSON of every quantitative field +
    the verdict + its basis. LLM narratives are EXCLUDED by construction —
    prose is narration; the reproducibility contract covers the numbers."""
    payload: dict[str, Any] = {
        "verdict": verdict,
        "basis": basis.model_dump(),
        "quant": {
            s.agent: {k: v.model_dump() for k, v in sorted(s.quant.items())}
            for s in sorted(sections, key=lambda x: x.agent)
        },
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
