"""boem_bsee connector tests — offline, on RECORDED-REAL fixtures.

Fixtures (verbatim lines, untrimmed fields, recorded 2026-07-18):

- tests/fixtures/boem_boreholes_sample.csv — the real header row + 15 rows
  copied verbatim from ``BoreholeRawData/mv_boreholes_all.txt``, recorded from
  https://www.data.boem.gov/Well/Files/BoreholeRawData.zip on 2026-07-18
  (full file: 57,446 rows). 12 REGION_CODE='G' rows covering type codes
  E/D/C/R/O, matched and unmatched exploratory wells, blank spud dates,
  a blank BH_TOTAL_MD, a '*****' proprietary-masked BH_TOTAL_MD, the literal
  NOLEASE and DPST lease values, an old leading-space lease (" 00023") on a
  multi-field lease, and an embedded-comma company name — plus one P, one A
  (type 'S'), and one Y region row to prove the Gulf scope filter.
- tests/fixtures/boem_mastdata_sample.txt — 9 headerless rows copied verbatim
  from ``mastdatadelimit.txt``, recorded from
  https://www.data.boem.gov/FieldReserves/Files/mastdatadelimit.zip on
  2026-07-18 (full file: 6,368 rows): the field-lease rows for every matched
  fixture well, both rows of multi-field lease " 00023" (WD027+WD030), and an
  embedded-comma operator row (EB158/G02647).
"""

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion.base import FetchResult, run_connector
from erda_labels.sources import boem_bsee

FIXTURES = Path(__file__).parent / "fixtures"
BOREHOLES = FIXTURES / "boem_boreholes_sample.csv"
MASTDATA = FIXTURES / "boem_mastdata_sample.txt"
OUTCOME_FRAGMENT = (
    Path(__file__).parents[3] / "data" / "curated" / "outcome_map.d" / "boem_bsee.csv"
)


def _boreholes() -> pd.DataFrame:
    return boem_bsee.read_boreholes(BOREHOLES)


def _field_leases() -> pd.DataFrame:
    return boem_bsee.read_field_leases(MASTDATA)


def _normalized() -> pd.DataFrame:
    return boem_bsee.normalize(_boreholes(), _field_leases())


def _row(df: pd.DataFrame, well_id: str) -> pd.Series:
    match = df[df["well_id"] == well_id]
    assert len(match) == 1, f"{well_id} not unique/found"
    return match.iloc[0]


def test_normalize_scope_and_no_dropped_rows():
    df = _normalized()
    # 15 fixture boreholes → 12 Gulf rows; P/A/Y regions are out of scope,
    # and within scope no row is dropped (§0/§5 law)
    assert len(df) == 12
    assert list(df.columns) == boem_bsee.COLUMNS
    assert df["well_id"].is_unique
    assert df["well_id"].str.startswith("boem:").all()
    for excluded in ["boem:043112005301", "boem:610400000100", "boem:500292107400"]:
        assert excluded not in set(df["well_id"])  # P / A / Y regions


def test_normalize_values_and_feet_conversion():
    df = _normalized()
    talos = _row(df, "boem:608174147600")  # Talos SS001, exploratory, unmatched lease
    assert talos["lat"] == pytest.approx(28.82296428)
    assert talos["lon"] == pytest.approx(-88.49290545)
    assert talos["spud_year"] == 2023
    assert talos["purpose_raw"] == "E"
    assert talos["purpose"] == "wildcat"
    assert talos["content_raw"] == "NO_FIELD_LEASE"
    # BH_TOTAL_MD is feet (BOEM record layout) → metres via the named constant
    assert talos["td_m"] == pytest.approx(16097 * boem_bsee.FT_TO_M)
    assert pd.isna(talos["discovery_id"])


def test_normalize_purpose_mapping_conflates_wildcat_appraisal():
    df = _normalized()
    assert _row(df, "boem:608174148000")["purpose"] == "wildcat"  # E, matched lease
    assert _row(df, "boem:608174147700")["purpose"] == "other"  # D development
    assert _row(df, "boem:608174115600")["purpose"] == "other"  # C core test
    assert _row(df, "boem:608174116300")["purpose"] == "other"  # R relief
    assert _row(df, "boem:608174149800")["purpose"] == "other"  # O other
    # BOEM has no wildcat/appraisal distinction — "appraisal" can never appear
    # for this source (documented limitation, carried on the dataset card)
    assert set(df["purpose"]) == {"wildcat", "other"}


def test_lease_proxy_join():
    df = _normalized()
    assert df["content_raw"].value_counts().to_dict() == {
        "FIELD_LEASE_MATCH": 7,
        "NO_FIELD_LEASE": 5,
    }
    # matched wells carry the field code(s) as discovery_id
    assert _row(df, "boem:608174148000")["discovery_id"] == "MC682"
    assert _row(df, "boem:608174147700")["discovery_id"] == "MC940"
    # old lease ' 00023' (leading space in BOTH files) matches after stripping;
    # its two fields join sorted and deterministic
    old = _row(df, "boem:177190005000")
    assert old["content_raw"] == "FIELD_LEASE_MATCH"
    assert old["discovery_id"] == "WD027+WD030"
    assert old["spud_year"] == 1953
    # literal NOLEASE / DPST lease values never match, by construction
    assert _row(df, "boem:608174026000")["content_raw"] == "NO_FIELD_LEASE"
    assert _row(df, "boem:608184005300")["content_raw"] == "NO_FIELD_LEASE"
    unmatched = df[df["content_raw"] == "NO_FIELD_LEASE"]
    assert unmatched["discovery_id"].isna().all()


def test_normalize_quirks_missing_stays_missing():
    df = _normalized()
    # blank WELL_SPUD_DATE → Int64 NA, row kept (harmonize drops-and-counts later)
    cancelled = _row(df, "boem:608224000200")
    assert pd.isna(cancelled["spud_year"])
    assert pd.isna(cancelled["td_m"])  # blank BH_TOTAL_MD stays missing
    assert pd.isna(_row(df, "boem:608244001200")["spud_year"])
    assert df["spud_year"].dtype == "Int64"
    # '*****' = BOEM's proprietary-period depth masking (2023-24 spuds) — an
    # explicit withheld sentinel: td_m stays missing, the row and its match stay
    masked = _row(df, "boem:608174148700")
    assert pd.isna(masked["td_m"])
    assert masked["spud_year"] == 2023
    assert masked["content_raw"] == "FIELD_LEASE_MATCH"
    assert masked["discovery_id"] == "MC392"
    # embedded comma in a quoted company name must not shift columns:
    # the Kosmos core test still lands on its real lease and matches
    kosmos = _row(df, "boem:608174115600")
    assert kosmos["content_raw"] == "FIELD_LEASE_MATCH"
    assert kosmos["discovery_id"] == "MC773"


def test_normalize_unknown_type_code_raises():
    boreholes = _boreholes()
    boreholes.loc[boreholes.index[1], "WELL_TYPE_CODE"] = "X"
    with pytest.raises(ContractViolation, match="'X'"):
        boem_bsee.normalize(boreholes, _field_leases())


def test_normalize_malformed_spud_raises():
    boreholes = _boreholes()
    boreholes.loc[boreholes.index[1], "WELL_SPUD_DATE"] = "2023-03-16"
    with pytest.raises(ContractViolation, match="format drifted"):
        boem_bsee.normalize(boreholes, _field_leases())


def test_normalize_empty_inputs_raise_not_empty_frame():
    no_gulf = _boreholes()
    no_gulf["REGION_CODE"] = "P"  # every row out of scope
    with pytest.raises(ContractViolation, match="zero REGION_CODE"):
        boem_bsee.normalize(no_gulf, _field_leases())

    # an empty field-lease master would silently mark every well NO_FIELD_LEASE
    empty_master = _field_leases().iloc[0:0]
    with pytest.raises(ContractViolation, match="master is empty"):
        boem_bsee.normalize(_boreholes(), empty_master)

    with pytest.raises(ContractViolation, match="missing columns"):
        boem_bsee.normalize(_boreholes().drop(columns=["BOTM_LEASE_NUMBER"]), _field_leases())


def test_read_field_leases_rejects_layout_drift():
    nine_columns = io.StringIO('"AC024","G10379","AC","24","960024","X","OCT-1998","T",""\n')
    with pytest.raises(ContractViolation, match="expected 10"):
        boem_bsee.read_field_leases(nine_columns)


def test_normalize_hard_duplicate_collapses_conflicting_raises(tmp_path):
    boreholes = _boreholes()
    doubled = pd.concat([boreholes, boreholes.iloc[[1]]], ignore_index=True)
    df = boem_bsee.normalize(doubled, _field_leases())
    assert len(df) == 12  # identical duplicate by PK collapsed

    twin = boreholes.iloc[[1]].copy()
    twin["BH_TOTAL_MD"] = "99999"  # same PK, different data
    conflicting = pd.concat([boreholes, twin], ignore_index=True)
    bad = boem_bsee.normalize(conflicting, _field_leases())  # both survive → contract fails

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=boem_bsee.BOREHOLE_ZIP_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=boem_bsee.SOURCE_ID,
            transform_version=boem_bsee.TRANSFORM_VERSION,
            schema=boem_bsee.SCHEMA,
            fetch=fake_fetch,
            table=boem_bsee.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = _normalized()

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=boem_bsee.BOREHOLE_ZIP_URL)

    entry = run_connector(
        source_id=boem_bsee.SOURCE_ID,
        transform_version=boem_bsee.TRANSFORM_VERSION,
        schema=boem_bsee.SCHEMA,
        fetch=fake_fetch,
        table=boem_bsee.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 12
    written = pd.read_parquet(tmp_path / "boem_bsee_wells.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "boem_bsee").all()
    assert (written["transform_version"] == "boem_bsee:1.0.0").all()
    assert read_ledger(tmp_path)[0].table == "boem_bsee_wells"


def _zip_bytes(member: str, payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(member, payload)
    return buf.getvalue()


def test_fetch_end_to_end_through_recorded_zips(monkeypatch):
    """fetch() unzips both downloads exactly as BOEM packages them."""
    responses = {
        # real member layout: a folder prefix in the borehole zip, bare in the master
        boem_bsee.BOREHOLE_ZIP_URL: _zip_bytes(
            "BoreholeRawData/mv_boreholes_all.txt", BOREHOLES.read_bytes()
        ),
        boem_bsee.MASTDATA_ZIP_URL: _zip_bytes("mastdatadelimit.txt", MASTDATA.read_bytes()),
    }

    def fake_http_get(url, source_id, **kwargs):
        return SimpleNamespace(content=responses[url])

    monkeypatch.setattr(boem_bsee, "http_get", fake_http_get)
    result = boem_bsee.fetch()
    assert result.source_url == boem_bsee.BOREHOLE_ZIP_URL
    assert len(result.frame) == 12
    assert result.frame["content_raw"].isin(["FIELD_LEASE_MATCH", "NO_FIELD_LEASE"]).all()


def test_fetch_bad_zip_raises(monkeypatch):
    def fake_http_get(url, source_id, **kwargs):
        return SimpleNamespace(content=b"<html>maintenance page</html>")

    monkeypatch.setattr(boem_bsee, "http_get", fake_http_get)
    with pytest.raises(SourceUnavailable, match="not a zip"):
        boem_bsee.fetch()

    with pytest.raises(SourceUnavailable, match="exactly one"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("a.txt", b"x")
            archive.writestr("b.txt", b"y")
        boem_bsee.extract_member(buf.getvalue(), "borehole zip")


def test_outcome_fragment_covers_every_observed_code():
    """Both proxy codes have cited outcome-map rows; nothing else is invented."""
    fragment = pd.read_csv(OUTCOME_FRAGMENT, dtype=str, keep_default_na=False)
    assert (fragment["source_id"] == "boem_bsee").all()
    assert fragment["content_raw"].is_unique
    assert (fragment["source_url"].str.strip() != "").all()  # §7: cited or rejected
    assert fragment["label"].isin(["0", "1"]).all()
    assert fragment["shows"].isin(["true", "false"]).all()
    # the lease proxy carries no shows information — shows must be false throughout
    assert (fragment["shows"] == "false").all()
    # the proxy caveat must be stated where the label is defined
    match_note = fragment.set_index("content_raw").loc["FIELD_LEASE_MATCH", "notes"]
    assert "PROXY" in match_note.upper()

    observed = set(_normalized()["content_raw"])
    mapped = set(fragment["content_raw"])
    assert observed == mapped == {"FIELD_LEASE_MATCH", "NO_FIELD_LEASE"}
