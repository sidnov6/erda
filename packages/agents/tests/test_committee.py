"""Committee tests: full graph on the synthetic snapshot with the template
narrator — offline, deterministic, §11.3 re-run hash proven identical."""

import pandas as pd
import pytest

from erda_agents.committee import BlockRequest, run_committee
from erda_agents.narrators import TemplateNarrator


@pytest.fixture()
def full_ctx(ctx):
    root = ctx.repo_root
    strip = pd.DataFrame(
        {
            "asof_date": pd.to_datetime(["2026-07-18"] * 2),
            "month_index": [1, 2],
            "contract": ["CLQ26.NYM", "CLU26.NYM"],
            "expiry": pd.to_datetime(["2026-08-20", "2026-09-21"]),
            "settle_usd_bbl": [82.49, 81.78],
            "indicative": [True, True],
        }
    )
    strip.to_parquet(root / "data" / "parquet" / "yf_curve_strip.parquet")
    # engine mapping on the synthetic fiscal file
    (root / "data" / "curated" / "fiscal" / "TST.yaml").write_text(
        "iso3: TST\nregime_type: tax_royalty\nroyalty_rate: 0.1\ncit_rate: 0.3\n"
        "engine_mapping: {royalty_rate: 0.1, cit_rate: 0.3}\n"
        "source_urls: [https://example.com/tax]\n"
    )
    return ctx


REQUEST = BlockRequest(
    block_id="TEST-BLOCK-1",
    lat=60.0,
    lon=2.0,
    iso3="TST",
    country_name="Testland",
    host_distance_km=30.0,
    pg=0.25,
    resource_p90_p50_p10=(60.0, 100.0, 160.0),
    well_cost_musd=80.0,
)


def test_committee_produces_memo_with_all_laws(full_ctx):
    memo, payloads = run_committee(full_ctx, REQUEST, TemplateNarrator())
    assert memo.verdict in ("GO", "CONDITIONAL", "NO_GO")
    agents = {s.agent for s in memo.sections}
    assert agents == {
        "geoscience", "fiscal", "political_risk", "infrastructure",
        "environment", "financeability", "economist",
    }
    assert memo.citation_coverage >= 0.9
    assert memo.redteam_narrative  # required section present
    assert memo.verdict_basis.pg_provenance.startswith("user-supplied")
    # WDPA table absent in the synthetic snapshot → environment reports the gap
    env = next(s for s in memo.sections if s.agent == "environment")
    assert "data_gap" in env.quant
    # every quant field cites something (schema-enforced, belt+braces)
    for section in memo.sections:
        for field in section.quant.values():
            assert field.source_ids


def test_memo_rerun_hash_is_identical(full_ctx):
    memo_a, _ = run_committee(full_ctx, REQUEST, TemplateNarrator())
    memo_b, _ = run_committee(full_ctx, REQUEST, TemplateNarrator())
    assert memo_a.quant_hash == memo_b.quant_hash  # §11.3 determinism
    assert memo_a.verdict == memo_b.verdict
    # a different Pg changes the hash (the basis is inside it)
    memo_c, _ = run_committee(
        full_ctx, {**REQUEST, "pg": 0.30}, TemplateNarrator()
    )
    assert memo_c.quant_hash != memo_a.quant_hash
