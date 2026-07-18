import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import fred
from erda_ingestion.base import FetchResult, run_connector

FIXTURE = Path(__file__).parent / "fixtures" / "fred_observations_sample.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_normalize_drops_missing_and_types():
    df = fred.normalize("DCOILBRENTEU", _payload())
    # the "." observation on 2026-07-02 is missing data → dropped, never imputed
    assert len(df) == 2
    assert df["value"].tolist() == [74.10, 75.02]
    assert df["metric"].unique().tolist() == ["brent_usd_bbl"]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_normalize_error_body_raises_not_empty_frame():
    # a payload without "observations" (e.g. a FRED error body) must raise,
    # never normalize into an empty-but-fresh table
    payload = {"error_code": 400, "error_message": "Bad Request. Variable api_key is not set."}
    with pytest.raises(SourceUnavailable, match="api_key is not set"):
        fred.normalize("DCOILBRENTEU", payload)


def test_fetch_without_key_raises(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(SourceUnavailable, match="FRED_API_KEY"):
        fred.fetch()


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = fred.normalize("DCOILBRENTEU", _payload())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=fred.API_URL)

    entry = run_connector(
        source_id=fred.SOURCE_ID,
        transform_version=fred.TRANSFORM_VERSION,
        schema=fred.SCHEMA,
        fetch=fake_fetch,
        table=fred.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 2
    written = pd.read_parquet(tmp_path / "fred_series.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "fred").all()
    assert read_ledger(tmp_path)[0].table == "fred_series"


def test_runner_rejects_contract_violation(tmp_path):
    bad = fred.normalize("DCOILBRENTEU", _payload())
    bad.loc[0, "value"] = -1.0  # negative price violates the contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=fred.API_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=fred.SOURCE_ID,
            transform_version=fred.TRANSFORM_VERSION,
            schema=fred.SCHEMA,
            fetch=fake_fetch,
            table=fred.TABLE,
            root=tmp_path,
        )
    # nothing bad persisted, ledger untouched
    assert read_ledger(tmp_path) == []
