"""nlog connector tests — offline, on a RECORDED-REAL fixture.

Fixture: tests/fixtures/nlog_wfs_sample.geojson — 20 features copied verbatim
from the live WFS GetFeature response, recorded from
https://www.gdngeoservices.nl/geoserver/nlog/ows?service=WFS&version=2.0.0
&request=GetFeature&typeNames=nlog:gdw_ng_wll_all_utm&srsName=EPSG:4326
&outputFormat=application/json on 2026-07-18 (full response: 6,728 features).
Counts were rewritten to the trimmed size; feature contents are untouched. The
sample covers all 15 observed BOREHOLE_RESULT_CODE values plus the null result,
wildcat/appraisal/other type codes, a sidetrack, a null END_DEPTH_MAH, and the
1800 spud-year edge.
"""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion.base import FetchResult, run_connector
from erda_labels.sources import nlog

FIXTURE = Path(__file__).parent / "fixtures" / "nlog_wfs_sample.geojson"
OUTCOME_FRAGMENT = Path(__file__).parents[3] / "data" / "curated" / "outcome_map.d" / "nlog.csv"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text())


def _row(df: pd.DataFrame, well_id: str) -> pd.Series:
    match = df[df["well_id"] == well_id]
    assert len(match) == 1, f"{well_id} not unique/found"
    return match.iloc[0]


def test_normalize_shape_and_no_dropped_rows():
    df = nlog.normalize(_payload())
    # every fixture feature survives — rows are never dropped (§0/§5 law)
    assert len(df) == 20
    assert list(df.columns) == nlog.COLUMNS
    assert df["well_id"].is_unique
    assert df["well_id"].str.startswith("nlog:").all()


def test_normalize_axis_order_and_values():
    df = nlog.normalize(_payload())
    hil = _row(df, "nlog:HIL-01")  # HILVERSUM-01: ~52.24N, 5.05E — lat/lon must not swap
    assert hil["lat"] == pytest.approx(52.24475194)
    assert hil["lon"] == pytest.approx(5.04831408)
    assert hil["spud_year"] == 1944
    assert hil["purpose_raw"] == "EXP-HC"
    assert hil["purpose"] == "wildcat"
    assert hil["content_raw"] == "FLR"
    assert hil["td_m"] == pytest.approx(732.2)
    assert pd.isna(hil["discovery_id"])


def test_normalize_purpose_mapping():
    df = nlog.normalize(_payload())
    assert _row(df, "nlog:DB-001")["purpose"] == "wildcat"  # legacy EXP code
    assert _row(df, "nlog:HLO-02")["purpose"] == "appraisal"  # EVA-HC
    assert _row(df, "nlog:G17-A-01-S1")["purpose"] == "other"  # DEV-HC development
    assert _row(df, "nlog:SM-02")["purpose"] == "other"  # EXP-C coal
    assert _row(df, "nlog:HLH-GT-02")["purpose"] == "other"  # DEV-PH geothermal
    # nothing filtered at connector level — harmonize selects wildcats later
    assert set(df["purpose"]) == {"wildcat", "appraisal", "other"}


def test_normalize_quirks_stay_verbatim():
    df = nlog.normalize(_payload())
    # null BOREHOLE_RESULT_CODE → explicit empty string, never dropped/guessed
    assert _row(df, "nlog:DB-001")["content_raw"] == ""
    # null END_DEPTH_MAH stays missing
    assert pd.isna(_row(df, "nlog:HKS-H-01")["td_m"])
    # 1800 spud year is genuine history — kept (harmonize applies its own floor)
    assert _row(df, "nlog:SM-02")["spud_year"] == 1800
    assert df["spud_year"].dtype == "Int64"
    # sidetracks are separate wellbores with their own PK
    assert _row(df, "nlog:GTV-01-S1")["content_raw"] == "OIL"
    # FIELD_CODE → discovery_id when present
    assert _row(df, "nlog:GRT-01")["discovery_id"] == "GRT"


def test_normalize_unknown_type_code_raises():
    payload = _payload()
    payload["features"][0]["properties"]["BOREHOLE_TYPE_CODE"] = "EXP-HC-CCS"
    with pytest.raises(ContractViolation, match="EXP-HC-CCS"):
        nlog.normalize(payload)


def test_normalize_missing_pk_raises():
    payload = _payload()
    payload["features"][3]["properties"]["BOREHOLE_CODE"] = None
    with pytest.raises(ContractViolation, match="BOREHOLE_CODE"):
        nlog.normalize(payload)


def test_normalize_empty_or_truncated_raises_not_empty_frame():
    empty = _payload()
    empty["features"] = []
    with pytest.raises(SourceUnavailable, match="zero features"):
        nlog.normalize(empty)

    truncated = _payload()
    truncated["numberMatched"] = 6728  # server paged the response — partial data
    with pytest.raises(SourceUnavailable, match="truncated"):
        nlog.normalize(truncated)

    with pytest.raises(SourceUnavailable, match="features"):
        nlog.normalize({"error": "not geojson"})


def test_normalize_hard_duplicate_collapses_conflicting_raises(tmp_path):
    payload = _payload()
    payload["features"].append(copy.deepcopy(payload["features"][0]))
    df = nlog.normalize(payload)
    assert len(df) == 20  # identical duplicate by PK collapsed

    conflicting = _payload()
    twin = copy.deepcopy(conflicting["features"][0])
    twin["properties"]["END_DEPTH_MAH"] = 9999.0  # same PK, different data
    conflicting["features"].append(twin)
    bad = nlog.normalize(conflicting)  # both rows survive to fail the contract loudly

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=nlog.WFS_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=nlog.SOURCE_ID,
            transform_version=nlog.TRANSFORM_VERSION,
            schema=nlog.SCHEMA,
            fetch=fake_fetch,
            table=nlog.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = nlog.normalize(_payload())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=nlog.WFS_URL)

    entry = run_connector(
        source_id=nlog.SOURCE_ID,
        transform_version=nlog.TRANSFORM_VERSION,
        schema=nlog.SCHEMA,
        fetch=fake_fetch,
        table=nlog.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 20
    written = pd.read_parquet(tmp_path / "nlog_wells.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "nlog").all()
    assert (written["transform_version"] == "nlog:1.0.0").all()
    assert read_ledger(tmp_path)[0].table == "nlog_wells"


def test_outcome_fragment_covers_every_observed_code():
    """Every content_raw the connector can emit has a cited outcome-map row.

    The fragment must be read with keep_default_na=False so the blank-result
    row ("" content_raw) survives — the merged-map assembler must do the same.
    """
    fragment = pd.read_csv(OUTCOME_FRAGMENT, dtype=str, keep_default_na=False)
    assert (fragment["source_id"] == "nlog").all()
    assert fragment["content_raw"].is_unique
    assert (fragment["source_url"].str.strip() != "").all()  # §7: cited or rejected
    assert fragment["label"].isin(["0", "1"]).all()
    assert fragment["shows"].isin(["true", "false"]).all()
    # discoveries are never flagged as shows — shows drives a 0-label sensitivity
    assert fragment[(fragment["label"] == "1") & (fragment["shows"] == "true")].empty

    df = nlog.normalize(_payload())
    observed = set(df["content_raw"])
    mapped = set(fragment["content_raw"])
    assert observed <= mapped, f"unmapped codes: {sorted(observed - mapped)}"
    # the fixture exercises the full live inventory: 15 codes + blank
    assert len(observed) == 16
