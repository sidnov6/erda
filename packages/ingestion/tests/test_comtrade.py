import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import comtrade
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = FIXTURES / "comtrade_preview_annual_2023.json"
CAPPED = FIXTURES / "comtrade_preview_capped_2023.json"


def _clean_payload() -> dict:
    return json.loads(CLEAN.read_text())


def _capped_payload() -> dict:
    return json.loads(CAPPED.read_text())


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_normalize_clean_preview_shape_and_flags():
    df = comtrade.normalize(_clean_payload())
    assert list(df.columns) == comtrade.COLUMNS
    assert len(df) == 6
    assert (df["year"] == 2023).all()
    # count=101 < 500 → not the preview cap, nothing truncated
    assert (~df["truncated"]).all()
    # world aggregates are isReported=false/isAggregate=true → UN-derived estimate
    assert df["is_estimate"].all()
    by_iso = df.set_index("reporter_iso")
    assert by_iso.loc["AND", "export_value_usd"] == pytest.approx(19.466)
    assert by_iso.loc["USA", "export_value_usd"] == pytest.approx(117160520564.0)
    assert by_iso.loc["AGO", "reporter"] == "Angola"
    assert pd.api.types.is_integer_dtype(df["year"])
    assert pd.api.types.is_float_dtype(df["export_value_usd"])
    assert pd.api.types.is_bool_dtype(df["truncated"])


def test_normalize_marks_cap_truncated_and_drops_breakdown_rows():
    df = comtrade.normalize(_capped_payload())
    # fixture holds 4 world-aggregate rows + 4 partner2/mot/customs breakdown
    # rows that duplicate them — keeping those would double-count exports
    assert len(df) == 4
    assert not df.duplicated(["year", "reporter_iso"]).any()
    # count == 500 is the keyless preview hard cap → every row marked truncated
    assert df["truncated"].all()
    by_iso = df.set_index("reporter_iso")
    assert by_iso.loc["AGO", "export_value_usd"] == pytest.approx(31419862877.569)


def test_normalize_drops_missing_values_never_imputes():
    payload = _clean_payload()
    payload["data"][0]["primaryValue"] = None  # missing value
    payload["data"][1]["reporterISO"] = None  # missing reporter identity
    df = comtrade.normalize(payload)
    assert len(df) == 4
    assert df["export_value_usd"].notna().all()


def test_fetch_keyless_uses_preview_endpoint(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    calls = []

    def fake_http_get(url, source_id, *, params=None, headers=None, **kw):
        calls.append({"url": url, "params": params, "headers": headers})
        return _FakeResponse(_clean_payload())

    monkeypatch.setattr(comtrade, "http_get", fake_http_get)
    result = comtrade.fetch(years=(2023,))
    assert calls[0]["url"] == comtrade.PREVIEW_URL
    assert calls[0]["headers"] is None
    assert calls[0]["params"]["period"] == "2023"
    assert calls[0]["params"]["cmdCode"] == "2709"
    assert len(result.frame) == 6
    assert result.source_url == comtrade.PREVIEW_URL


def test_fetch_with_key_uses_keyed_endpoint_header_and_throttle(monkeypatch):
    monkeypatch.setenv("COMTRADE_API_KEY", "test-key-123")
    calls: list[dict] = []
    sleeps: list[float] = []

    def fake_http_get(url, source_id, *, params=None, headers=None, **kw):
        calls.append({"url": url, "headers": headers})
        return _FakeResponse(_clean_payload())

    monkeypatch.setattr(comtrade, "http_get", fake_http_get)
    monkeypatch.setattr(comtrade.time, "sleep", sleeps.append)
    result = comtrade.fetch(years=(2022, 2023))
    assert all(c["url"] == comtrade.KEYED_URL for c in calls)
    assert all(c["headers"] == {"Ocp-Apim-Subscription-Key": "test-key-123"} for c in calls)
    assert sleeps == [1.0]  # 1 req/s throttle between the two calls
    # provenance URL never carries the key
    assert "test-key-123" not in result.source_url


def test_fetch_api_error_raises(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    payload = {"count": 0, "data": [], "error": "quota exceeded"}
    monkeypatch.setattr(comtrade, "http_get", lambda *a, **kw: _FakeResponse(payload))
    with pytest.raises(SourceUnavailable, match="quota exceeded"):
        comtrade.fetch(years=(2023,))


def test_fetch_no_rows_any_year_raises(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    payload = {"count": 0, "data": [], "error": ""}
    monkeypatch.setattr(comtrade, "http_get", lambda *a, **kw: _FakeResponse(payload))
    with pytest.raises(SourceUnavailable, match="no data"):
        comtrade.fetch(years=(2023, 2024))


def test_fetch_drifted_shape_raises_not_empty_table(monkeypatch):
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)
    payload = _capped_payload()
    # keep only breakdown rows: data present but nothing matches the world-
    # aggregate slice → shape/params drift must fail loudly, not persist nothing
    payload["data"] = [
        r
        for r in payload["data"]
        if not (
            r["partner2Code"] == 0 and r["motCode"] == 0 and r["customsCode"] == "C00"
        )
    ]
    assert payload["data"]
    monkeypatch.setattr(comtrade, "http_get", lambda *a, **kw: _FakeResponse(payload))
    with pytest.raises(SourceUnavailable, match="drifted"):
        comtrade.fetch(years=(2023,))


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = comtrade.normalize(_clean_payload())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=comtrade.PREVIEW_URL)

    entry = run_connector(
        source_id=comtrade.SOURCE_ID,
        transform_version=comtrade.TRANSFORM_VERSION,
        schema=comtrade.SCHEMA,
        fetch=fake_fetch,
        table=comtrade.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 6
    written = pd.read_parquet(tmp_path / "comtrade_crude_exports.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "comtrade").all()
    assert (written["transform_version"] == "comtrade:1.0.0").all()
    assert read_ledger(tmp_path)[0].table == "comtrade_crude_exports"


def test_runner_rejects_contract_violation(tmp_path):
    bad = comtrade.normalize(_clean_payload())
    bad.loc[0, "export_value_usd"] = -5.0  # negative export value violates contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=comtrade.PREVIEW_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=comtrade.SOURCE_ID,
            transform_version=comtrade.TRANSFORM_VERSION,
            schema=comtrade.SCHEMA,
            fetch=fake_fetch,
            table=comtrade.TABLE,
            root=tmp_path,
        )
    # nothing bad persisted, ledger untouched
    assert read_ledger(tmp_path) == []
