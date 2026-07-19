import copy
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import wgi
from erda_ingestion.base import FetchResult, run_connector

FIXTURE = Path(__file__).parent / "fixtures" / "wgi_nga_nor_2020_2024.json"

#: Recorded live on 2026-07-19 — the HTTP-200 body the API returns when a
#: multi-indicator query omits source=3 (fixtures README).
MESSAGE_BODY = [
    {
        "message": [
            {
                "id": "120",
                "key": "Invalid value",
                "value": "The provided parameter value is not valid",
            }
        ]
    }
]


def _payload() -> list:
    return json.loads(FIXTURE.read_text())


def test_normalize_strips_prefix_and_types():
    df = wgi.normalize(_payload())
    # 2 countries × 6 indicators × 5 years, no nulls in the recorded window
    assert len(df) == 60
    assert sorted(df["indicator"].unique()) == sorted(wgi.INDICATORS)
    assert not df["indicator"].str.startswith("GOV_WGI_").any()
    assert sorted(df["iso3"].unique()) == ["NGA", "NOR"]
    assert pd.api.types.is_integer_dtype(df["year"])
    assert pd.api.types.is_float_dtype(df["value"])
    nga_cc_2024 = df[(df.iso3 == "NGA") & (df.indicator == "CC.EST") & (df.year == 2024)]
    assert nga_cc_2024["value"].item() == pytest.approx(-1.1145909)


def test_normalize_drops_null_values_absent_never_zero():
    payload = copy.deepcopy(_payload())
    payload[1][0]["value"] = None  # NGA CC.EST 2024 in the recorded fixture
    df = wgi.normalize(payload)
    assert len(df) == 59
    dropped = df[(df.iso3 == "NGA") & (df.indicator == "CC.EST") & (df.year == 2024)]
    assert dropped.empty
    assert not (df["value"] == 0.0).any()  # never imputed to zero


def test_normalize_drops_rows_without_iso3():
    # 9 territories (e.g. Taiwan, China) come back with empty countryiso3code —
    # they cannot key an iso3 table and are dropped, documented in the module
    payload = copy.deepcopy(_payload())
    payload[1][0]["countryiso3code"] = ""
    assert len(wgi.normalize(payload)) == 59


def test_normalize_message_body_raises_not_empty_frame():
    with pytest.raises(SourceUnavailable, match="not valid"):
        wgi.normalize(MESSAGE_BODY)


def test_normalize_empty_rows_raise():
    meta = {"page": 1, "pages": 0, "per_page": 2000, "total": 0}
    with pytest.raises(SourceUnavailable, match="no data rows"):
        wgi.normalize([meta, None])
    with pytest.raises(SourceUnavailable, match="no data rows"):
        wgi.normalize([meta, []])


def test_normalize_all_null_values_raise():
    payload = copy.deepcopy(_payload())
    for row in payload[1]:
        row["value"] = None
    with pytest.raises(SourceUnavailable, match="none carried a value"):
        wgi.normalize(payload)


def test_pv_beyond_nominal_scale_is_valid_history(tmp_path):
    # WGI's scale is only *approximately* ±2.5 — YEM PV.EST 2024 = −2.7506
    # live; the contract must accept it (module docstring)
    payload = copy.deepcopy(_payload())
    pv_rows = [r for r in payload[1] if r["indicator"]["id"] == "GOV_WGI_PV.EST"]
    pv_rows[0]["value"] = -2.7505641
    frame = wgi.normalize(payload)

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=wgi.BASE_URL)

    entry = run_connector(
        source_id=wgi.SOURCE_ID,
        transform_version=wgi.TRANSFORM_VERSION,
        schema=wgi.SCHEMA,
        fetch=fake_fetch,
        table=wgi.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 60


def test_fetch_decodes_bom_and_concatenates(monkeypatch):
    # some live responses carry a UTF-8 BOM (registry note) — fetch must
    # decode utf-8-sig; exercised offline by stubbing the transport
    fixture_rows = _payload()[1]

    def fake_http_get(url, source_id, *, params=None, headers=None, **kw):
        code = "GOV_WGI_" + url.rsplit("GOV_WGI_", 1)[1]
        rows = [r for r in fixture_rows if r["indicator"]["id"] == code]
        assert params["source"] == "3"  # mandatory param (registry drift note)
        meta = {"page": 1, "pages": 1, "per_page": 2000, "total": len(rows)}
        body = b"\xef\xbb\xbf" + json.dumps([meta, rows]).encode()
        return httpx.Response(200, content=body)

    monkeypatch.setattr(wgi, "http_get", fake_http_get)
    result = wgi.fetch()
    assert len(result.frame) == 60
    assert sorted(result.frame["indicator"].unique()) == sorted(wgi.INDICATORS)
    assert result.source_url == wgi.BASE_URL


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = wgi.normalize(_payload())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=wgi.BASE_URL)

    entry = run_connector(
        source_id=wgi.SOURCE_ID,
        transform_version=wgi.TRANSFORM_VERSION,
        schema=wgi.SCHEMA,
        fetch=fake_fetch,
        table=wgi.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 60
    written = pd.read_parquet(tmp_path / "wgi_governance.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "wgi").all()
    assert read_ledger(tmp_path)[0].table == "wgi_governance"


def test_runner_rejects_contract_violation(tmp_path):
    bad = wgi.normalize(_payload())
    bad.loc[0, "indicator"] = "XX.EST"  # not one of the six WGI dimensions

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=wgi.BASE_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=wgi.SOURCE_ID,
            transform_version=wgi.TRANSFORM_VERSION,
            schema=wgi.SCHEMA,
            fetch=fake_fetch,
            table=wgi.TABLE,
            root=tmp_path,
        )
    # nothing bad persisted, ledger untouched
    assert read_ledger(tmp_path) == []
