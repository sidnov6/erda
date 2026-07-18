"""Memo-core tests (spec §10.3/§10.6/§11.3): schema law, verdict rules, hash."""

import pytest
from pydantic import ValidationError

from erda_agents import verdict
from erda_agents.memo_schema import (
    MemoSection,
    QuantField,
    VerdictBasis,
    citation_coverage,
    quant_hash,
)


def _basis(**overrides) -> VerdictBasis:
    base = dict(
        emv_musd=447.35,
        p_emv_positive=0.72,
        sanctions_flag=False,
        wdpa_overlap_pct=0.0,
        pg=0.25,
        pg_provenance="user-supplied (§9.8 — no model Pg ships)",
    )
    return VerdictBasis(**{**base, **overrides})


def test_uncited_number_is_unrepresentable():
    with pytest.raises(ValidationError):
        QuantField(value=1.0, source_ids=[])
    with pytest.raises(ValidationError):
        QuantField(value=1.0, source_ids=["  "])
    ok = QuantField(value=447.35, unit="MUSD", source_ids=["erda_engine"])
    assert ok.source_ids == ["erda_engine"]


def test_verdict_rules_exact():
    assert verdict.decide(_basis()) == "GO"
    assert verdict.decide(_basis(sanctions_flag=True)) == "NO_GO"
    assert verdict.decide(_basis(wdpa_overlap_pct=25.1)) == "NO_GO"
    assert verdict.decide(_basis(emv_musd=0.0)) == "NO_GO"
    assert verdict.decide(_basis(emv_musd=-10.0)) == "NO_GO"
    assert verdict.decide(_basis(p_emv_positive=0.59)) == "CONDITIONAL"
    assert verdict.decide(_basis(wdpa_overlap_pct=10.1)) == "CONDITIONAL"
    # boundary semantics: 10% overlap is still GO, 25% is CONDITIONAL
    assert verdict.decide(_basis(wdpa_overlap_pct=10.0)) == "GO"
    assert verdict.decide(_basis(wdpa_overlap_pct=25.0)) == "CONDITIONAL"
    # sanctions dominates everything
    assert verdict.decide(_basis(sanctions_flag=True, emv_musd=1e9)) == "NO_GO"


def test_citation_coverage_counts():
    sections = [
        MemoSection(
            agent="fiscal",
            quant={"cit_rate": QuantField(value=0.22, source_ids=["curated_fiscal"])},
        ),
        MemoSection(agent="redteam", narrative="risks…", quant={}),
    ]
    assert citation_coverage(sections) == 1.0


def test_quant_hash_stable_and_prose_independent():
    basis = _basis()
    quant = {"emv_musd": QuantField(value=447.35, unit="MUSD", source_ids=["erda_engine"])}
    a = [MemoSection(agent="economist", narrative="one wording", quant=quant)]
    b = [MemoSection(agent="economist", narrative="ANOTHER wording entirely", quant=quant)]
    v = verdict.decide(basis)
    assert quant_hash(a, v, basis) == quant_hash(b, v, basis)  # prose excluded
    # any quantitative change breaks the hash
    c = [
        MemoSection(
            agent="economist",
            quant={"emv_musd": QuantField(value=447.36, unit="MUSD", source_ids=["erda_engine"])},
        )
    ]
    assert quant_hash(a, v, basis) != quant_hash(c, v, basis)
    # section order does not matter (canonicalized)
    two = [
        MemoSection(agent="b", quant=quant),
        MemoSection(agent="a", quant=quant),
    ]
    assert quant_hash(two, v, basis) == quant_hash(list(reversed(two)), v, basis)
