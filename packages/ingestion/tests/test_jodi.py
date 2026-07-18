"""Offline tests for the jodi connector — fixture recorded 2026-07-18, no network.

Fixture: header + 1450 real rows from world_Primary_CSV.zip (see fixtures/README.md).
Coverage: US/SA/NO 2025-12+2026-01, AE 2026-01, ZA 2008-12; all four OBS_VALUE
absence markers ('-', 'x', 'N/A', '..'); negative STATDIFF values.
"""

from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import jodi
from erda_ingestion.base import FetchResult, run_connector

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "jodi_world_primary_sample.csv"
FIXTURE_ZIP = Path(__file__).parent / "fixtures" / "jodi_world_primary_sample.zip"


def _raw() -> pd.DataFrame:
    with FIXTURE_CSV.open("rb") as handle:
        return jodi.read_raw(handle)


def test_read_raw_preserves_absence_markers_as_literals():
    raw = _raw()
    # keep_default_na=False must stop pandas from eating the 'N/A' marker
    markers = set(raw["OBS_VALUE"]) & jodi.ABSENCE_MARKERS
    assert markers == {"-", "x", "N/A", ".."}


def test_normalize_filters_to_crudeoil_and_drops_absence_markers():
    df = jodi.normalize(_raw())
    # fixture holds 400 CRUDEOIL rows; 88 '-' + 16 'x' + 20 'N/A' + 6 '..' are
    # absence markers (never zeros) → dropped, leaving 270
    assert len(df) == 270
    assert df["energy_product"].unique().tolist() == ["CRUDEOIL"]
    # dropped, not imputed: ZA 2008-12 DIRECUSE/OSOURCES/STATDIFF/TRANSBAK are
    # 'N/A' in the recorded file (all 5 units) → absent entirely, never 0.0
    za = df[(df["ref_area"] == "ZA") & (df["period"] == pd.Timestamp("2008-12-01"))]
    assert set(za["flow_breakdown"]) & {"DIRECUSE", "OSOURCES", "STATDIFF", "TRANSBAK"} == set()
    assert df["value"].notna().all()


def test_normalize_values_periods_and_negatives():
    df = jodi.normalize(_raw())
    us = df[
        (df["ref_area"] == "US")
        & (df["period"] == pd.Timestamp("2026-01-01"))
        & (df["flow_breakdown"] == "INDPROD")
        & (df["unit_measure"] == "KBD")
    ]
    assert us["value"].tolist() == [13246.3871]
    assert us["assessment_code"].tolist() == ["1"]
    # TIME_PERIOD 'YYYY-MM' → month-start timestamps
    assert pd.api.types.is_datetime64_any_dtype(df["period"])
    assert (df["period"].dt.day == 1).all()
    # negative statistical differences are real data, kept as-is
    no = df[
        (df["ref_area"] == "NO")
        & (df["period"] == pd.Timestamp("2025-12-01"))
        & (df["flow_breakdown"] == "STATDIFF")
        & (df["unit_measure"] == "KBD")
    ]
    assert no["value"].tolist() == [-28.2913]


def test_normalize_empty_product_slice_raises():
    # a drifted product codelist must fail loudly, never persist an empty table
    with pytest.raises(ContractViolation, match="codelist drifted"):
        jodi.normalize(_raw(), product="NOTAPRODUCT")


def test_normalize_rejects_unknown_marker():
    raw = _raw()
    raw.loc[raw["OBS_VALUE"] == "13246.3871", "OBS_VALUE"] = "??"
    with pytest.raises(ContractViolation, match="unrecognized OBS_VALUE"):
        jodi.normalize(raw)


def test_normalize_rejects_missing_columns():
    with pytest.raises(ContractViolation, match="missing columns"):
        jodi.normalize(pd.DataFrame({"REF_AREA": ["US"]}))


def test_extract_csv_from_recorded_zip():
    raw = jodi.extract_csv(FIXTURE_ZIP.read_bytes())
    assert list(raw.columns) == jodi.RAW_COLUMNS
    assert len(raw) == 1450


def test_extract_csv_rejects_garbage():
    with pytest.raises(SourceUnavailable, match="not a zip"):
        jodi.extract_csv(b"this is not a zip archive")


def test_extract_csv_rejects_wrong_member_count(tmp_path):
    import zipfile

    path = tmp_path / "two.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("a.csv", "REF_AREA\n")
        zf.writestr("b.csv", "REF_AREA\n")
    with pytest.raises(SourceUnavailable, match="exactly one CSV"):
        jodi.extract_csv(path.read_bytes())


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = jodi.normalize(_raw())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=jodi.ZIP_URL)

    entry = run_connector(
        source_id=jodi.SOURCE_ID,
        transform_version=jodi.TRANSFORM_VERSION,
        schema=jodi.SCHEMA,
        fetch=fake_fetch,
        table=jodi.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 270
    written = pd.read_parquet(tmp_path / "jodi_oil.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "jodi").all()
    assert (written["source_url"] == jodi.ZIP_URL).all()
    assert read_ledger(tmp_path)[0].table == "jodi_oil"


def test_runner_rejects_contract_violation(tmp_path):
    bad = jodi.normalize(_raw())
    bad.loc[0, "unit_measure"] = "BARRELS"  # not in the pinned unit codelist

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=jodi.ZIP_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=jodi.SOURCE_ID,
            transform_version=jodi.TRANSFORM_VERSION,
            schema=jodi.SCHEMA,
            fetch=fake_fetch,
            table=jodi.TABLE,
            root=tmp_path,
        )
    # nothing persisted, ledger untouched
    assert read_ledger(tmp_path) == []


def test_runner_rejects_duplicate_series_key(tmp_path):
    dup = jodi.normalize(_raw())
    dup = pd.concat([dup, dup.iloc[[0]]], ignore_index=True)

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=dup, source_url=jodi.ZIP_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=jodi.SOURCE_ID,
            transform_version=jodi.TRANSFORM_VERSION,
            schema=jodi.SCHEMA,
            fetch=fake_fetch,
            table=jodi.TABLE,
            root=tmp_path,
        )
