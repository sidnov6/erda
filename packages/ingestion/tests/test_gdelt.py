"""Offline tests for the gdelt connector — no network, ever (skill §2.7).

Fixtures:
- gdelt_artlist_sample.json — SYNTHETIC TEST ARTIFACT (spec §11.3); artlist
  fields were not live-confirmable (endpoint IP-throttled at the 2026-07-18
  sweep and at build time).
- gdelt_throttle_429.txt — REAL response body, recorded verbatim from
  https://api.gdeltproject.org/api/v2/doc/doc on 2026-07-18 (HTTP 429).
"""

import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import gdelt
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
ARTLIST_FIXTURE = FIXTURES / "gdelt_artlist_sample.json"
# Recorded from https://api.gdeltproject.org/api/v2/doc/doc on 2026-07-18.
THROTTLE_FIXTURE = FIXTURES / "gdelt_throttle_429.txt"


def _payload() -> dict:
    return json.loads(ARTLIST_FIXTURE.read_text())


def _fake_response(status_code: int, body: str) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=body.encode(),
        request=httpx.Request("GET", gdelt.API_URL),
    )


def _no_spacing(monkeypatch):
    """Reset the module rate-limit state so offline tests never sleep."""
    monkeypatch.setattr(gdelt, "_last_request_at", None)


# --- normalize -------------------------------------------------------------


def test_normalize_defensive_missing_keys_and_dedupe():
    df = gdelt.normalize(_payload())
    # 6 synthetic articles: 1 lacks url (dropped), 1 is a duplicate url (deduped)
    assert len(df) == 4
    assert df["url"].is_unique
    assert "https://news.example.com/hormuz-tanker-delay" in df["url"].tolist()
    # dedupe keeps the FIRST occurrence, not the syndication copy
    first = df.set_index("url").loc["https://news.example.com/hormuz-tanker-delay"]
    assert first["title"] == "Tanker transit delayed near Strait of Hormuz"
    # missing title → null (None/NaN), never invented
    row = df.set_index("url").loc["https://wire.example.org/pipeline-outage"]
    assert pd.isna(row["title"])
    assert pd.isna(row["source_country"])
    # garbled seendate → NaT; missing seendate → NaT
    assert pd.isna(row["seen_at"])
    malacca = df.set_index("url").loc["https://sea.example.sg/malacca-advisory"]
    assert pd.isna(malacca["seen_at"])
    # confirmed timestamps parse to tz-aware UTC
    assert isinstance(df["seen_at"].dtype, pd.DatetimeTZDtype)
    hormuz = df.set_index("url").loc["https://news.example.com/hormuz-tanker-delay"]
    assert hormuz["seen_at"] == pd.Timestamp("2026-07-18T04:15:00Z")
    # theme_tags records the query filter, comma-joined
    assert (df["theme_tags"] == gdelt.THEME_TAGS).all()


def test_normalize_empty_or_absent_articles_yields_empty_frame():
    for payload in ({}, {"articles": []}, {"articles": None}):
        df = gdelt.normalize(payload)
        assert len(df) == 0
        assert list(df.columns) == gdelt.COLUMNS


def test_normalize_skips_non_dict_entries():
    df = gdelt.normalize({"articles": ["garbage", 42, {"url": "https://x.example.com/a"}]})
    assert df["url"].tolist() == ["https://x.example.com/a"]


# --- fetch failure paths (network stubbed) ---------------------------------


def test_fetch_429_throttle_body_raises_ip_throttled(monkeypatch):
    _no_spacing(monkeypatch)
    body = THROTTLE_FIXTURE.read_text()
    assert gdelt.THROTTLE_MARKER in body  # marker matches the recorded body
    monkeypatch.setattr(gdelt.httpx, "get", lambda *a, **kw: _fake_response(429, body))
    with pytest.raises(SourceUnavailable, match="IP throttled"):
        gdelt.fetch()


def test_fetch_429_unknown_body_still_raises(monkeypatch):
    _no_spacing(monkeypatch)
    monkeypatch.setattr(gdelt.httpx, "get", lambda *a, **kw: _fake_response(429, "slow down"))
    with pytest.raises(SourceUnavailable, match="429"):
        gdelt.fetch()


def test_fetch_200_non_json_raises_not_papered_over(monkeypatch):
    _no_spacing(monkeypatch)
    monkeypatch.setattr(
        gdelt.httpx,
        "get",
        lambda *a, **kw: _fake_response(200, "Your query was too short or too long."),
    )
    with pytest.raises(SourceUnavailable, match="non-JSON"):
        gdelt.fetch()


def test_min_spacing_enforced_between_requests(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(gdelt.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(gdelt, "_last_request_at", None)
    gdelt._wait_for_spacing()
    assert sleeps == []  # first request: no wait
    gdelt._wait_for_spacing()
    assert len(sleeps) == 1  # immediate second request must wait
    assert 0 < sleeps[0] <= gdelt._MIN_SPACING_S


# --- run_connector integration (fake fetch, tmp_path) ----------------------


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = gdelt.normalize(_payload())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=gdelt.API_URL)

    entry = run_connector(
        source_id=gdelt.SOURCE_ID,
        transform_version=gdelt.TRANSFORM_VERSION,
        schema=gdelt.SCHEMA,
        fetch=fake_fetch,
        table=gdelt.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 4
    written = pd.read_parquet(tmp_path / "gdelt_events.parquet")
    # every persisted row carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "gdelt").all()
    assert (written["transform_version"] == "gdelt:1.0.0").all()
    assert read_ledger(tmp_path)[0].table == "gdelt_events"


def test_runner_rejects_contract_violation(tmp_path):
    bad = gdelt.normalize(_payload())
    bad.loc[0, "url"] = None  # null url violates the contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=gdelt.API_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=gdelt.SOURCE_ID,
            transform_version=gdelt.TRANSFORM_VERSION,
            schema=gdelt.SCHEMA,
            fetch=fake_fetch,
            table=gdelt.TABLE,
            root=tmp_path,
        )
    # nothing persisted, ledger untouched
    assert read_ledger(tmp_path) == []
