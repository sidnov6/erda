import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import eia_v2
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "eia_v2_seriesid_sample.json"  # SYNTHETIC (spec §11.3)
ERROR_403 = FIXTURES / "eia_v2_error_403.json"  # recorded live 2026-07-18


def _payload() -> dict:
    return json.loads(SAMPLE.read_text())


def test_normalize_drops_null_and_coerces_types():
    df = eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", _payload())
    # the null value on 2026-07-03 is a missing datum → dropped, never imputed
    assert len(df) == 2
    # string-typed "415000" and numeric 416200 both coerce to float
    assert df["value"].tolist() == [415000.0, 416200.0]
    assert df["metric"].unique().tolist() == ["crude_stocks_excl_spr_kbbl"]
    assert df["series_id"].unique().tolist() == ["PET.WCESTUS1.W"]
    assert pd.api.types.is_datetime64_any_dtype(df["period"])


def test_normalize_403_error_body_maps_to_source_unavailable():
    # keyless v2 returns 403 with this exact JSON (recorded 2026-07-18);
    # an error body must never normalize into empty data
    payload = json.loads(ERROR_403.read_text())
    with pytest.raises(SourceUnavailable, match="API_KEY_MISSING"):
        eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", payload)


def test_normalize_truncated_response_raises():
    payload = _payload()
    payload["response"]["total"] = 999  # claims more rows than delivered
    with pytest.raises(SourceUnavailable, match="truncated"):
        eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", payload)


def test_normalize_empty_data_list_raises():
    # pinned WPSR series always have history; an empty data list is upstream
    # failure/drift, never an empty-but-fresh table
    payload = _payload()
    payload["response"]["data"] = []
    payload["response"]["total"] = 0
    with pytest.raises(SourceUnavailable, match="empty"):
        eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", payload)


def test_normalize_malformed_payload_raises():
    with pytest.raises(SourceUnavailable, match="malformed"):
        eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", {"response": None})


def test_fetch_without_key_raises(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    with pytest.raises(SourceUnavailable, match="EIA_API_KEY"):
        eia_v2.fetch()


def test_load_series_pins_are_cited():
    # the real curated file: five WPSR series, every row carries its doc URL (§7)
    pins = eia_v2.load_series()
    assert [p["series_id"] for p in pins] == [
        "PET.WCESTUS1.W",
        "PET.WGTSTUS1.W",
        "PET.WDISTUS1.W",
        "PET.WCRFPUS2.W",
        "PET.WRPUPUS2.W",
    ]
    for pin in pins:
        assert pin["source_url"].startswith("https://www.eia.gov/")
        assert pin["metric"].endswith(("_kbbl", "_kbd"))  # units in the name


def test_load_series_rejects_uncited_row(tmp_path):
    uncited = tmp_path / "eia_series.yaml"
    uncited.write_text(
        "series:\n  - series_id: PET.WCESTUS1.W\n    metric: crude_stocks_excl_spr_kbbl\n"
    )
    with pytest.raises(ContractViolation, match="source_url"):
        eia_v2.load_series(uncited)


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", _payload())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=eia_v2.API_URL)

    entry = run_connector(
        source_id=eia_v2.SOURCE_ID,
        transform_version=eia_v2.TRANSFORM_VERSION,
        schema=eia_v2.SCHEMA,
        fetch=fake_fetch,
        table=eia_v2.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 2
    written = pd.read_parquet(tmp_path / "eia_v2_weekly.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "eia_v2").all()
    assert read_ledger(tmp_path)[0].table == "eia_v2_weekly"


def test_runner_rejects_contract_violation(tmp_path):
    bad = eia_v2.normalize("PET.WCESTUS1.W", "crude_stocks_excl_spr_kbbl", _payload())
    bad.loc[bad.index[0], "value"] = -5.0  # negative stocks violate the contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=eia_v2.API_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=eia_v2.SOURCE_ID,
            transform_version=eia_v2.TRANSFORM_VERSION,
            schema=eia_v2.SCHEMA,
            fetch=fake_fetch,
            table=eia_v2.TABLE,
            root=tmp_path,
        )
    # nothing bad persisted, ledger untouched
    assert read_ledger(tmp_path) == []
