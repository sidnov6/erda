"""Offline tests for the opec MOMR connector. Fixtures are real recorded pages
(see fixtures/README.md); no network is touched anywhere here."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import opec
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
TABLE_PDF = FIXTURES / "opec_momr_june2026_table5_7.pdf"
NO_TABLE_PDF = FIXTURES / "opec_momr_june2026_notable.pdf"

OPEC_12 = {
    "Algeria",
    "Congo",
    "Equatorial Guinea",
    "Gabon",
    "IR Iran",
    "Iraq",
    "Kuwait",
    "Libya",
    "Nigeria",
    "Saudi Arabia",
    "UAE",
    "Venezuela",
}


def _kbd(df: pd.DataFrame, country: str, month: str) -> float:
    row = df[(df["country"] == country) & (df["month"] == pd.Timestamp(month))]
    assert len(row) == 1
    return row["production_kbd"].iloc[0]


def test_normalize_parses_opec_members_by_month():
    df = opec.normalize(TABLE_PDF.read_bytes())
    # 12 members x 3 monthly columns (annual/quarterly averages are excluded)
    assert set(df["country"]) == OPEC_12
    assert sorted(df["month"].unique()) == [
        pd.Timestamp("2026-03-01"),
        pd.Timestamp("2026-04-01"),
        pd.Timestamp("2026-05-01"),
    ]
    assert len(df) == 36
    assert pd.api.types.is_datetime64_any_dtype(df["month"])
    # spot checks against the printed June 2026 MOMR, Table 5-7
    assert _kbd(df, "Algeria", "2026-05-01") == 982.0
    assert _kbd(df, "Saudi Arabia", "2026-03-01") == 7626.0
    assert _kbd(df, "IR Iran", "2026-05-01") == 2330.0
    assert _kbd(df, "Venezuela", "2026-04-01") == 1036.0
    # spec §4: scraped MOMR numbers are flagged
    assert (df["extraction"] == "semi_automated").all()
    # aggregates are not observations
    assert not df["country"].str.startswith("Total").any()


def test_normalize_reads_secondary_sources_not_direct_communication():
    # The same page carries Table 5-8 "based on direct communication" where Iraq
    # reports 1,759 for May; secondary sources say 1,481. Matching the wrong
    # table would also import ".." rows (Gabon/Iran are blank there).
    df = opec.normalize(TABLE_PDF.read_bytes())
    assert _kbd(df, "Iraq", "2026-05-01") == 1481.0
    assert _kbd(df, "Gabon", "2026-05-01") == 214.0
    assert df["production_kbd"].notna().all()


def test_normalize_without_table_raises():
    # Real page 55: mentions "secondary sources" in prose but holds no table.
    with pytest.raises(ContractViolation, match="secondary sources"):
        opec.normalize(NO_TABLE_PDF.read_bytes())


def test_clean_value_sentinels():
    assert opec._clean_value("1,036") == 1036.0
    assert opec._clean_value("7,763*") == 7763.0  # footnote marker stripped
    assert opec._clean_value("..") is None  # MOMR "not available"
    assert opec._clean_value("-") is None
    assert opec._clean_value("-546") == -546.0


def test_candidate_urls_cover_registry_irregulars():
    urls = opec.candidate_urls("June", 2026)
    base = "https://www.opec.org/assets/assetdb/"
    assert urls[0] == f"{base}momr-june-2026.pdf"  # canonical pattern first
    assert f"{base}momr-june-2026-1.pdf" in urls  # "-1" irregular suffix
    assert f"{base}momr-jun-2026.pdf" in urls  # abbreviated month
    assert f"{base}momr-jun-2026-1.pdf" in urls


def test_fetch_all_candidates_missing_raises(monkeypatch):
    tried = []

    def gone(url, source_id, **kwargs):
        tried.append(url)
        raise SourceUnavailable(source_id, f"{url} → 404")

    monkeypatch.setattr(opec, "http_get", gone)
    with pytest.raises(SourceUnavailable, match="no open MOMR PDF"):
        opec.fetch(month_name="june", year=2026)
    assert len(tried) == 4  # every candidate probed before giving up


def test_fetch_returns_first_working_candidate(monkeypatch):
    good = "https://www.opec.org/assets/assetdb/momr-june-2026.pdf"

    def fake_get(url, source_id, **kwargs):
        if url == good:
            return SimpleNamespace(content=TABLE_PDF.read_bytes())
        raise SourceUnavailable(source_id, f"{url} → 404")

    monkeypatch.setattr(opec, "http_get", fake_get)
    result = opec.fetch(month_name="june", year=2026)
    assert result.source_url == good
    assert len(result.frame) == 36


def test_fetch_rejects_non_pdf_body(monkeypatch):
    # Cloudflare interstitials return HTML with 200 — never parsed as data.
    monkeypatch.setattr(
        opec, "http_get", lambda url, source_id, **kw: SimpleNamespace(content=b"<html>block")
    )
    with pytest.raises(SourceUnavailable, match="no open MOMR PDF"):
        opec.fetch(month_name="june", year=2026)


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = opec.normalize(TABLE_PDF.read_bytes())
    url = "https://www.opec.org/assets/assetdb/momr-june-2026.pdf"

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=url)

    entry = run_connector(
        source_id=opec.SOURCE_ID,
        transform_version=opec.TRANSFORM_VERSION,
        schema=opec.SCHEMA,
        fetch=fake_fetch,
        table=opec.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 36
    written = pd.read_parquet(tmp_path / "opec_production.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "opec").all()
    assert (written["extraction"] == "semi_automated").all()
    assert read_ledger(tmp_path)[0].table == "opec_production"


def test_runner_rejects_contract_violation(tmp_path):
    bad = opec.normalize(TABLE_PDF.read_bytes())
    bad.loc[0, "production_kbd"] = -5.0  # negative production violates the contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url="https://www.opec.org/x.pdf")

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=opec.SOURCE_ID,
            transform_version=opec.TRANSFORM_VERSION,
            schema=opec.SCHEMA,
            fetch=fake_fetch,
            table=opec.TABLE,
            root=tmp_path,
        )
    # nothing bad persisted, ledger untouched
    assert read_ledger(tmp_path) == []
