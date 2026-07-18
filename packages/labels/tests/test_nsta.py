"""nsta connector tests — offline, on a RECORDED-REAL fixture.

fixtures/nsta_top_holes_sample.json was recorded from
https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/UKCS_offshore_wellbore_top_holes_(WGS84)/FeatureServer/0/query
on 2026-07-18 (where=WELLREGNO IN (13 named E&A wellbores) plus a second
recorded query for WELLREGNO='13/21a- 8'; outFields=*,
orderByFields=OBJECTID, f=json) — unmodified ArcGIS response features
chosen to cover the quirk matrix: negative epoch-ms SPUDDATE (41/18- 2,
1966), null FLOWCLASS (C48/30- 21, C44/27- 3), null TDTVDSSM (C44/27- 3,
106/24a- 2B), literal-zero TDTVDSSM (13/21a- 1), negative-convention
TDTVDSSM (13/21a- 8, −930.55 m), null TOPHOLEXDD/YDD with geometry
present (41/18- 2), the TARGETFLD "No Data Available" sentinel vs a real
field (CAPTAIN), and both ORIGINTENT values.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion.base import FetchResult, run_connector
from erda_labels.sources import nsta

FIXTURE = Path(__file__).parent / "fixtures" / "nsta_top_holes_sample.json"


def _page() -> dict:
    return json.loads(FIXTURE.read_text())


def _row(df: pd.DataFrame, well_id: str) -> pd.Series:
    match = df[df["well_id"] == well_id]
    assert len(match) == 1, f"{well_id} not unique/found"
    return match.iloc[0]


def test_normalize_maps_all_rows_verbatim():
    df = nsta.normalize([_page()])
    assert len(df) == 14  # nothing dropped
    assert df["well_id"].str.startswith("nsta:").all()
    # purpose mapping: Exploration → wildcat, Appraisal → appraisal —
    # except carbon-storage registrations (C-prefix), which are "other"
    petroleum = ~df["well_id"].str.match(r"nsta:C\d")
    assert (df.loc[petroleum & (df["purpose_raw"] == "Exploration"), "purpose"] == "wildcat").all()
    assert (df.loc[petroleum & (df["purpose_raw"] == "Appraisal"), "purpose"] == "appraisal").all()
    assert df["purpose"].value_counts().to_dict() == {"wildcat": 9, "appraisal": 3, "other": 2}
    # content codes verbatim; null FLOWCLASS → explicit "" (never guessed dry)
    assert _row(df, "nsta:C48/30- 21")["content_raw"] == ""
    assert _row(df, "nsta:13/22b- 4")["content_raw"] == "Gas and Condensate Well"
    assert _row(df, "nsta:108/30- 1")["content_raw"] == "Unknown"


def test_carbon_storage_registrations_never_map_to_wildcat_or_appraisal():
    # The E&A WHERE clause does NOT exclude CCS: the fixture's two CS-licence
    # wells (C48/30- 21 "Hewett CCS Appraisal well" by Bacton CCS Ltd, and
    # C44/27- 3 by Net Zero North Sea Storage) carry ORIGINTENT='Appraisal'.
    # CO2-store probes are not petroleum exploration — purpose must be
    # "other" (the sodir WILDCAT-CCS lesson), with ORIGINTENT kept verbatim.
    df = nsta.normalize([_page()])
    for well in ["nsta:C48/30- 21", "nsta:C44/27- 3"]:
        row = _row(df, well)
        assert row["purpose_raw"] == "Appraisal"  # verbatim, never rewritten
        assert row["purpose"] == "other"

    # a CS well recorded with ORIGINTENT='Exploration' must not become a
    # wildcat either — that would poison the primary label set
    page = _page()
    for feature in page["features"]:
        if feature["attributes"]["WELLREGNO"] == "C44/27- 3":
            feature["attributes"]["ORIGINTENT"] = "Exploration"
    df = nsta.normalize([page])
    assert _row(df, "nsta:C44/27- 3")["purpose"] == "other"


def test_normalize_spud_year_handles_negative_epoch_ms():
    df = nsta.normalize([_page()])
    # SPUDDATE −110160000000 ms (pre-1970) → 1966, not an overflow or drop
    assert _row(df, "nsta:41/18- 2")["spud_year"] == 1966
    assert _row(df, "nsta:C48/30- 21")["spud_year"] == 2025
    assert df["spud_year"].dtype == pd.Int64Dtype()


def test_normalize_prefers_geometry_over_dd_strings():
    page = _page()
    df = nsta.normalize([page])
    # C48/30- 21 has BOTH: geometry y=53.0021955…, DD string "53.002987…"
    # (different top-hole reduction) — geometry must win.
    row = _row(df, "nsta:C48/30- 21")
    assert row["lat"] == pytest.approx(53.0021955350615)
    assert row["lon"] == pytest.approx(1.83488818080911)
    # 41/18- 2 has null DD strings but a real geometry → coords present
    row = _row(df, "nsta:41/18- 2")
    assert row["lat"] == pytest.approx(54.3918269695294)


def test_normalize_dd_fallback_and_missing_coords_stay_missing():
    page = _page()
    for feature in page["features"]:
        if feature["attributes"]["WELLREGNO"] == "C48/30- 21":
            del feature["geometry"]  # force the DD-string fallback
        if feature["attributes"]["WELLREGNO"] == "41/18- 2":
            del feature["geometry"]  # DD strings are null too → missing
    df = nsta.normalize([page])
    assert _row(df, "nsta:C48/30- 21")["lat"] == pytest.approx(53.002987777777776)
    # both coordinate carriers absent → missing, row KEPT (14 rows still)
    assert pd.isna(_row(df, "nsta:41/18- 2")["lat"])
    assert len(df) == 14


def test_normalize_malformed_dd_string_raises_not_coerces():
    page = _page()
    for feature in page["features"]:
        if feature["attributes"]["WELLREGNO"] == "C48/30- 21":
            del feature["geometry"]
            feature["attributes"]["TOPHOLEYDD"] = "fifty-three degrees"
    with pytest.raises(ContractViolation, match="TOPHOLEYDD"):
        nsta.normalize([page])


def test_normalize_missing_and_sentinel_values():
    df = nsta.normalize([_page()])
    assert pd.isna(_row(df, "nsta:C44/27- 3")["td_m"])  # null stays missing
    assert _row(df, "nsta:13/21a- 1")["td_m"] == 0.0  # published 0 kept verbatim
    # TARGETFLD sentinel "No Data Available" → missing; real name verbatim
    assert pd.isna(_row(df, "nsta:11/24- 1")["discovery_id"])
    assert _row(df, "nsta:13/21a- 1")["discovery_id"] == "CAPTAIN"


def test_normalize_flips_negative_convention_td():
    # 25/5,129 live records store TVDSS negative-down (elevation
    # convention); 13/21a- 8 is one (TVDSSM −930.55, MD 1010.41 m
    # corroborates) → sign-flipped to the dominant positive-down metres
    df = nsta.normalize([_page()])
    row = _row(df, "nsta:13/21a- 8")
    assert row["td_m"] == pytest.approx(930.5543985855572)
    assert row["spud_year"] == 2018


def test_normalize_error_body_raises_not_empty_frame():
    # ArcGIS reports failures as HTTP 200 + error body — must raise
    payload = {"error": {"code": 400, "message": "Invalid query parameters"}}
    with pytest.raises(SourceUnavailable, match="Invalid query parameters"):
        nsta.normalize([payload])


def test_normalize_zero_features_raises():
    with pytest.raises(SourceUnavailable, match="empty-but-fresh"):
        nsta.normalize([{"features": []}])


def test_normalize_missing_required_field_is_drift_and_raises():
    # a silent upstream rename of FLOWCLASS would blank every label — the
    # missing KEY must raise, never normalize to excluded-class ""
    page = _page()
    for feature in page["features"]:
        del feature["attributes"]["FLOWCLASS"]
    with pytest.raises(ContractViolation, match="FLOWCLASS"):
        nsta.normalize([page])


def test_normalize_unexpected_origintent_raises():
    page = _page()
    page["features"][0]["attributes"]["ORIGINTENT"] = "Development"
    with pytest.raises(ContractViolation, match="Development"):
        nsta.normalize([page])


def test_normalize_collapses_hard_duplicates_only():
    # pagination overlap re-serves identical rows → collapse to one
    df = nsta.normalize([_page(), _page()])
    assert len(df) == 14


def _fake_http_get(responses):
    calls = []

    def fake(url, source_id, *, params=None, **kwargs):
        calls.append(dict(params))
        payload = responses[len(calls) - 1]
        return SimpleNamespace(json=lambda: payload)

    return fake, calls


def test_fetch_paginates_until_transfer_limit_clears(monkeypatch):
    features = _page()["features"]
    pages = [
        {"features": features[:5], "exceededTransferLimit": True},
        {"features": features[5:10], "exceededTransferLimit": True},
        {"features": features[10:]},  # final page: no flag
    ]
    fake, calls = _fake_http_get(pages)
    monkeypatch.setattr(nsta, "http_get", fake)
    result = nsta.fetch(page_size=5)
    assert len(result.frame) == 14
    assert result.source_url == nsta.QUERY_URL
    assert [c["resultOffset"] for c in calls] == [0, 5, 10]
    assert all(c["where"] == nsta.WHERE for c in calls)


def test_fetch_arcgis_error_body_raises(monkeypatch):
    fake, _ = _fake_http_get([{"error": {"code": 499, "message": "Token Required"}}])
    monkeypatch.setattr(nsta, "http_get", fake)
    with pytest.raises(SourceUnavailable, match="Token Required"):
        nsta.fetch()


def test_fetch_runaway_pagination_raises(monkeypatch):
    # server ignoring resultOffset: every page claims more remains → raise
    # after MAX_PAGES, never return a possibly-partial table
    stuck = {"features": _page()["features"][:1], "exceededTransferLimit": True}
    fake, calls = _fake_http_get([stuck] * (nsta.MAX_PAGES + 1))
    monkeypatch.setattr(nsta, "http_get", fake)
    with pytest.raises(SourceUnavailable, match="did not terminate"):
        nsta.fetch(page_size=1)
    assert len(calls) == nsta.MAX_PAGES


def test_run_connector_full_path_writes_provenance_and_ledger(tmp_path):
    frame = nsta.normalize([_page()])

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=nsta.QUERY_URL)

    entry = run_connector(
        source_id=nsta.SOURCE_ID,
        transform_version=nsta.TRANSFORM_VERSION,
        schema=nsta.SCHEMA,
        fetch=fake_fetch,
        table=nsta.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 14
    written = pd.read_parquet(tmp_path / "nsta_wells.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "nsta").all()
    assert (written["transform_version"] == "nsta:1.0.0").all()
    assert read_ledger(tmp_path)[0].table == "nsta_wells"


def test_run_connector_rejects_out_of_range_coordinates(tmp_path):
    bad = nsta.normalize([_page()])
    bad.loc[0, "lat"] = 123.0  # impossible latitude violates the contract

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=nsta.QUERY_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=nsta.SOURCE_ID,
            transform_version=nsta.TRANSFORM_VERSION,
            schema=nsta.SCHEMA,
            fetch=fake_fetch,
            table=nsta.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []  # nothing bad persisted


def test_run_connector_rejects_conflicting_pk(tmp_path):
    # same PK with CONFLICTING payload survives normalize (not a hard
    # duplicate) and must fail the schema's uniqueness check loudly
    page = _page()
    clone = json.loads(json.dumps(page["features"][0]))
    clone["attributes"]["TDTVDSSM"] = 9999.0
    page["features"].append(clone)
    frame = nsta.normalize([page])
    assert len(frame) == 15  # conflict NOT silently resolved

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=nsta.QUERY_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=nsta.SOURCE_ID,
            transform_version=nsta.TRANSFORM_VERSION,
            schema=nsta.SCHEMA,
            fetch=fake_fetch,
            table=nsta.TABLE,
            root=tmp_path,
        )
