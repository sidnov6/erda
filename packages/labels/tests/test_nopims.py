"""nopims connector tests — offline, against recorded-real fixtures.

Fixtures (no values altered, envelopes preserved), both recorded 2026-07-18:

- tests/fixtures/nopims_odata_sample.json — 9 verbatim rows trimmed from the
  full 8,910-row pull of
  https://services.neats.nopta.gov.au/odata/v1/public/nopims/well/PublicNopimsWells
  ($select=Well_ID,Well,Borehole_ID,Borehole,Kick_Off_Date,Borehole_Reason,
  Drillers_TD_m,Offshore,Basin). Covers Exploration/Appraisal/Development/
  Stratigraphic Investigation/null Borehole_Reason, a null Kick_Off_Date, null
  Drillers_TD_m, a PNG-coordinate legacy well (Aramia 1), and one borehole
  with no spatial record (Barrow Island B24A, ENO0603892).
- tests/fixtures/nopims_arcgis_sample.json — the 8 matching verbatim features
  trimmed from the full 8,031-feature pull of
  https://arcgis.nopta.gov.au/arcgis/rest/services/Public/Petroleum_Wells/FeatureServer/0/query
  (outFields=Uwi,Ubhi,BHName,Latitude,Longitude,Purpose,Type,KickOffDate).
"""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion.base import FetchResult, run_connector
from erda_labels.sources import nopims

FIXTURES = Path(__file__).parent / "fixtures"
ODATA_FIXTURE = FIXTURES / "nopims_odata_sample.json"
ARCGIS_FIXTURE = FIXTURES / "nopims_arcgis_sample.json"


def _odata_rows() -> list[dict]:
    rows, next_link = nopims.parse_odata_page(json.loads(ODATA_FIXTURE.read_text()))
    assert next_link is None
    return rows


def _arcgis_attrs() -> list[dict]:
    attrs, exceeded = nopims.parse_arcgis_page(json.loads(ARCGIS_FIXTURE.read_text()))
    assert not exceeded
    return attrs


def _normalized() -> pd.DataFrame:
    return nopims.normalize(_odata_rows(), _arcgis_attrs())


# ————— normalize: correctness on recorded-real data —————


def test_normalize_shape_pk_and_documented_exclusion():
    df = _normalized()
    # 9 OData rows in, 8 out: ENO0603892 (Barrow Island B24A) has no spatial
    # record — the documented coordinate-gap exclusion, the only non-duplicate
    # row this connector removes.
    assert len(df) == 8
    assert list(df.columns) == nopims.COLUMNS
    assert df["well_id"].str.startswith("nopims:").all()
    assert df["well_id"].is_unique
    assert "nopims:ENO0603892" not in set(df["well_id"])


def test_normalize_spot_checked_real_row():
    # Goodwyn 1 (ENO0011753), NW Shelf exploration well spudded 1971.
    df = _normalized()
    row = df[df["well_id"] == "nopims:ENO0011753"].iloc[0]
    assert row["lat"] == pytest.approx(-19.692259)
    assert row["lon"] == pytest.approx(115.896772)
    assert row["spud_year"] == 1971
    assert row["purpose_raw"] == "Exploration"
    assert row["purpose"] == "wildcat"
    assert row["td_m"] == pytest.approx(3536.0)


def test_purpose_mapping_documented():
    df = _normalized().set_index("well_id")
    assert df.loc["nopims:ENO0007999", "purpose"] == "wildcat"  # Exploration
    assert df.loc["nopims:ENO0007996", "purpose"] == "appraisal"  # Appraisal
    assert df.loc["nopims:ENO0603290", "purpose"] == "other"  # Development
    assert df.loc["nopims:ENO0005861", "purpose"] == "other"  # Stratigraphic Investigation
    # null Borehole_Reason → verbatim empty string, purpose "other"
    assert df.loc["nopims:ENO0005755", "purpose_raw"] == ""
    assert df.loc["nopims:ENO0005755", "purpose"] == "other"


def test_missing_values_stay_missing():
    # ARMRAYNALD 1 (ENO0005838): no Kick_Off_Date, no Drillers_TD_m — the row
    # stays, the values stay missing; harmonize drops-and-counts downstream.
    df = _normalized().set_index("well_id")
    row = df.loc["nopims:ENO0005838"]
    assert pd.isna(row["spud_year"])
    assert pd.isna(row["td_m"])
    assert df["spud_year"].dtype == "Int64"


def test_non_australian_legacy_coordinates_kept_verbatim():
    # Aramia 1 (ENO0005807) is a Papuan Basin legacy record at ~7.8S — outside
    # any Australia bounding box. Geography is the downstream mask's job;
    # coordinates are never silently edited or dropped here.
    df = _normalized().set_index("well_id")
    assert df.loc["nopims:ENO0005807", "lat"] == pytest.approx(-7.829297)
    assert df.loc["nopims:ENO0005807", "lon"] == pytest.approx(142.3)


def test_no_outcome_source_yields_explicit_empty_content():
    # Australia contributes wells but no labels yet (module docstring): every
    # content_raw is the explicit "" mapped as excluded-class in
    # data/curated/outcome_map.d/nopims.csv; no discovery ids exist.
    df = _normalized()
    assert (df["content_raw"] == "").all()
    assert df["discovery_id"].isna().all()


def test_hard_duplicate_rows_collapse_conflicting_rows_survive():
    rows = _odata_rows()
    exact_dupe = copy.deepcopy(rows[0])
    df = nopims.normalize(rows + [exact_dupe], _arcgis_attrs())
    assert len(df) == 8  # identical record collapsed, nothing else touched

    conflicting = copy.deepcopy(rows[0])
    conflicting["Drillers_TD_m"] = 9999.0
    out = nopims.normalize(rows + [conflicting], _arcgis_attrs())
    # conflicting duplicate survives normalize and fails schema uniqueness
    assert (out["well_id"] == "nopims:" + rows[0]["Borehole_ID"]).sum() == 2
    with pytest.raises(ContractViolation):
        run_connector(
            source_id=nopims.SOURCE_ID,
            transform_version=nopims.TRANSFORM_VERSION,
            schema=nopims.SCHEMA,
            fetch=lambda: FetchResult(frame=out, source_url=nopims.ODATA_URL),
            table=nopims.TABLE,
            root=Path("/nonexistent-never-written"),
        )


# ————— failure paths: raise, never guess —————


def test_odata_error_body_raises_not_empty_frame():
    payload = {"error": {"code": "", "message": "The query specified in the URI is not valid."}}
    with pytest.raises(SourceUnavailable, match="not valid"):
        nopims.parse_odata_page(payload)


def test_arcgis_error_body_raises_despite_http_200():
    payload = {"error": {"code": 400, "message": "Unable to complete operation.", "details": []}}
    with pytest.raises(SourceUnavailable, match="Unable to complete"):
        nopims.parse_arcgis_page(payload)


def test_zero_rows_raise():
    with pytest.raises(SourceUnavailable, match="zero rows"):
        nopims.normalize([], _arcgis_attrs())
    with pytest.raises(SourceUnavailable, match="zero features"):
        nopims.normalize(_odata_rows(), [])


def test_zero_join_overlap_raises():
    attrs = copy.deepcopy(_arcgis_attrs())
    for i, a in enumerate(attrs):
        a["Ubhi"] = f"ENO99999{i:02d}"  # key drift: nothing matches
    with pytest.raises(SourceUnavailable, match="zero boreholes matched"):
        nopims.normalize(_odata_rows(), attrs)


def test_missing_fields_mean_endpoint_drift():
    rows = [{k: v for k, v in r.items() if k != "Borehole_Reason"} for r in _odata_rows()]
    with pytest.raises(SourceUnavailable, match="Borehole_Reason"):
        nopims.normalize(rows, _arcgis_attrs())
    attrs = [{k: v for k, v in a.items() if k != "Latitude"} for a in _arcgis_attrs()]
    with pytest.raises(SourceUnavailable, match="Latitude"):
        nopims.normalize(_odata_rows(), attrs)


def test_unmapped_borehole_reason_raises():
    rows = copy.deepcopy(_odata_rows())
    rows[0]["Borehole_Reason"] = "Extension Exploration"
    with pytest.raises(ContractViolation, match="Extension Exploration"):
        nopims.normalize(rows, _arcgis_attrs())


def test_conflicting_duplicate_spatial_record_raises():
    attrs = copy.deepcopy(_arcgis_attrs())
    twin = copy.deepcopy(attrs[0])
    twin["Latitude"] = twin["Latitude"] + 1.0  # same Ubhi, different location
    with pytest.raises(ContractViolation, match="join ambiguous"):
        nopims.normalize(_odata_rows(), attrs + [twin])


def test_drifted_kick_off_date_format_raises():
    rows = copy.deepcopy(_odata_rows())
    rows[0]["Kick_Off_Date"] = "20/04/1968"
    with pytest.raises(ContractViolation, match="format drifted"):
        nopims.normalize(rows, _arcgis_attrs())


def test_blank_borehole_id_raises():
    rows = copy.deepcopy(_odata_rows())
    rows[0]["Borehole_ID"] = None
    with pytest.raises(ContractViolation, match="blank Borehole_ID"):
        nopims.normalize(rows, _arcgis_attrs())


# ————— runner integration —————


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = _normalized()

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=nopims.ODATA_URL)

    entry = run_connector(
        source_id=nopims.SOURCE_ID,
        transform_version=nopims.TRANSFORM_VERSION,
        schema=nopims.SCHEMA,
        fetch=fake_fetch,
        table=nopims.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 8
    written = pd.read_parquet(tmp_path / "nopims_wells.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "nopims").all()
    assert (written["transform_version"] == "nopims:1.0.0").all()
    ledger = read_ledger(tmp_path)
    assert ledger[0].table == "nopims_wells"
    assert ledger[0].rows == 8


def test_runner_rejects_contract_violation(tmp_path):
    bad = _normalized()
    # if NOPTA ever starts publishing outcomes, the isin([""]) check must fail
    # loudly and force re-curation of the outcome map — silent ingestion of an
    # unmapped outcome code is the §5 nightmare.
    bad.loc[0, "content_raw"] = "GAS"

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=nopims.ODATA_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=nopims.SOURCE_ID,
            transform_version=nopims.TRANSFORM_VERSION,
            schema=nopims.SCHEMA,
            fetch=fake_fetch,
            table=nopims.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []
