"""Offline tests for the baker_hughes connector — no network, real recorded fixtures.

Fixtures (both recorded live on 2026-07-18, see fixtures/README.md):
- baker_hughes_nam_weekly_excerpt.xlsx — last two publish weeks of the real
  NAM Weekly sheet (weeks 2026-07-10 and 2026-07-17), banner + header layout
  preserved exactly as published.
- baker_hughes_na_rig_count_page.html — the full /na-rig-count page.
"""

from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import baker_hughes
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
XLSX_FIXTURE = FIXTURES / "baker_hughes_nam_weekly_excerpt.xlsx"
HTML_FIXTURE = FIXTURES / "baker_hughes_na_rig_count_page.html"


def _raw() -> pd.DataFrame:
    return baker_hughes.load_nam_weekly(XLSX_FIXTURE)


def _totals(df: pd.DataFrame, week: str) -> dict[str, int]:
    sub = df[df["week"] == pd.Timestamp(week)]
    return sub.groupby("region")["rig_count"].sum().to_dict()


def test_normalize_weekly_totals_match_published():
    df = baker_hughes.normalize(_raw())
    # Hand-checked against the recorded workbook: sum over all disaggregated
    # rows per publish week (the published US/Canada weekly headline counts).
    assert _totals(df, "2026-07-17") == {"us": 588, "canada": 198}
    assert _totals(df, "2026-07-10") == {"us": 581, "canada": 179}
    assert pd.api.types.is_datetime64_any_dtype(df["week"])
    assert pd.api.types.is_integer_dtype(df["rig_count"])
    assert set(df["drill_for"]) <= {"oil", "gas", "miscellaneous"}
    # aggregation key is unique — one row per (week, region, basin, drill_for)
    assert not df.duplicated(["week", "region", "basin", "drill_for"]).any()
    # basin detail survives: Permian present for the US, Canada published as "Other"
    assert "Permian" in set(df.loc[df["region"] == "us", "basin"])
    assert set(df.loc[df["region"] == "canada", "basin"]) == {"Other"}


def test_normalize_drops_incomplete_rows_never_imputes():
    raw = _raw()
    idx = raw.index[
        (raw["US_PublishDate"] == pd.Timestamp("2026-07-17"))
        & (raw["Country"] == "UNITED STATES")
    ][0]
    dropped = int(raw.loc[idx, "Rig Count Value"])
    raw.loc[idx, "Rig Count Value"] = None
    df = baker_hughes.normalize(raw)
    assert _totals(df, "2026-07-17")["us"] == 588 - dropped


def test_normalize_zero_surviving_rows_is_contract_violation():
    # headers intact but no data rows → drift, never an empty-but-fresh table
    with pytest.raises(ContractViolation, match="zero rows"):
        baker_hughes.normalize(_raw().iloc[0:0])


def test_normalize_missing_column_is_contract_violation():
    raw = _raw().drop(columns=["Rig Count Value"])
    with pytest.raises(ContractViolation, match="Rig Count Value"):
        baker_hughes.normalize(raw)


def test_normalize_unknown_country_is_contract_violation():
    raw = _raw()
    raw.loc[raw.index[0], "Country"] = "MEXICO"
    with pytest.raises(ContractViolation, match="MEXICO"):
        baker_hughes.normalize(raw)


def test_load_missing_sheet_is_contract_violation(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Wrong Sheet"
    path = tmp_path / "drifted.xlsx"
    wb.save(path)
    with pytest.raises(ContractViolation, match="NAM Weekly"):
        baker_hughes.load_nam_weekly(path)


def test_find_na_weekly_url_picks_latest_dated_anchor():
    url = baker_hughes.find_na_weekly_url(HTML_FIXTURE.read_text())
    # the recorded page's current report (07-17-2026) beats the Aug-2025 archive
    assert url == baker_hughes.NA_WEEKLY_URL


def test_find_na_weekly_url_without_anchor_raises():
    with pytest.raises(SourceUnavailable, match="anchor"):
        baker_hughes.find_na_weekly_url("<html><body><p>maintenance</p></body></html>")


def test_fetch_falls_back_to_page_scrape_when_uuid_fails(monkeypatch):
    """Simulate the registry's drift scenario: UUID 404s, page scrape recovers it."""
    calls: list[str] = []

    class FakeResp:
        def __init__(self, *, text: str = "", content: bytes = b""):
            self.text = text
            self.content = content

    def fake_download(url: str, **_kw) -> FakeResp:
        calls.append(url)
        if len(calls) == 1:  # first hit on the pinned UUID → down
            raise SourceUnavailable(baker_hughes.SOURCE_ID, f"{url} → 404")
        if url == baker_hughes.RIG_COUNT_PAGE_URL:
            return FakeResp(text=HTML_FIXTURE.read_text())
        return FakeResp(content=XLSX_FIXTURE.read_bytes())

    monkeypatch.setattr(baker_hughes, "_download", fake_download)
    result = baker_hughes.fetch()
    assert calls[0] == baker_hughes.NA_WEEKLY_URL
    assert calls[1] == baker_hughes.RIG_COUNT_PAGE_URL
    assert result.source_url == baker_hughes.NA_WEEKLY_URL  # page still points at same UUID
    assert _totals(result.frame, "2026-07-17") == {"us": 588, "canada": 198}


def test_fetch_raises_when_source_and_fallback_both_fail(monkeypatch):
    def dead(url: str, **_kw):
        raise SourceUnavailable(baker_hughes.SOURCE_ID, f"{url} → 404")

    monkeypatch.setattr(baker_hughes, "_download", dead)
    with pytest.raises(SourceUnavailable):
        baker_hughes.fetch()


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = baker_hughes.normalize(_raw())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=baker_hughes.NA_WEEKLY_URL)

    entry = run_connector(
        source_id=baker_hughes.SOURCE_ID,
        transform_version=baker_hughes.TRANSFORM_VERSION,
        schema=baker_hughes.SCHEMA,
        fetch=fake_fetch,
        table=baker_hughes.TABLE,
        root=tmp_path,
    )
    assert entry.rows == len(frame)
    written = pd.read_parquet(tmp_path / "baker_rigs.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "baker_hughes").all()
    assert (written["transform_version"] == "baker_hughes:1.0.0").all()
    assert read_ledger(tmp_path)[0].table == "baker_rigs"


def test_runner_rejects_contract_violation(tmp_path):
    bad = baker_hughes.normalize(_raw())
    bad.loc[0, "rig_count"] = -3  # negative rig count violates the contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=baker_hughes.NA_WEEKLY_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=baker_hughes.SOURCE_ID,
            transform_version=baker_hughes.TRANSFORM_VERSION,
            schema=baker_hughes.SCHEMA,
            fetch=fake_fetch,
            table=baker_hughes.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []
