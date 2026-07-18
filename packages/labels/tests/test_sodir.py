"""sodir connector tests — offline, against a recorded-real fixture.

Fixture: tests/fixtures/sodir_wellbore_exploration_sample.csv — 18 verbatim
CSV lines (byte-identical, CRLF + UTF-8 BOM preserved) trimmed from the
SSRS export
https://factpages.sodir.no/public?/Factpages/external/tableview/wellbore_exploration_all&rs:Command=Render&rc:Toolbar=false&rc:Parameters=f&rs:Format=CSV&Top100=false&IpAddress=not_used&CultureCode=en
(2,197 rows, 87 columns) recorded on 2026-07-18. Covers all 15 observed
wlbContent values, all 5 observed wlbPurpose values (incl. the CCS variants
and the one blank), a blank wlbEntryDate and a blank wlbTotalDepth. No values
were altered.
"""

import csv
import io
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion.base import FetchResult, run_connector
from erda_labels.sources import sodir

FIXTURE = Path(__file__).parent / "fixtures" / "sodir_wellbore_exploration_sample.csv"

#: Every wlbContent value observed in the full 2,197-row export on 2026-07-18;
#: the fixture covers each one, and each has a cited row in
#: data/curated/outcome_map.d/sodir.csv.
OBSERVED_CONTENT = {
    "DRY",
    "OIL",
    "OIL/GAS",
    "GAS",
    "GAS/CONDENSATE",
    "SHOWS",
    "OIL SHOWS",
    "",
    "NOT APPLICABLE",
    "GAS SHOWS",
    "OIL/GAS/CONDENSATE",
    "OIL/GAS SHOWS",
    "WATER",
    "WATER/GAS",
    "NOT AVAILABLE",
}


def _text() -> str:
    # plain utf-8 (not utf-8-sig) so the BOM survives — exactly what
    # httpx's resp.text hands to normalize().
    return FIXTURE.read_text(encoding="utf-8")


def _mutate(edit) -> str:
    """Parse the fixture, apply ``edit(header, rows)``, re-serialize as CSV."""
    reader = csv.reader(io.StringIO(_text().lstrip("\ufeff")))
    header, *rows = list(reader)
    edit(header, rows)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def test_normalize_shape_columns_and_pk():
    df = sodir.normalize(_text())
    # 18 recorded rows in → 18 rows out: nothing dropped, nothing invented
    assert len(df) == 18
    assert list(df.columns) == sodir.COLUMNS
    assert df["well_id"].str.startswith("sodir:").all()
    assert df["well_id"].is_unique
    # the BOM-carrying first column parsed as wlbWellboreName, not '﻿wlb…'
    assert "sodir:1/2-1" in set(df["well_id"])


def test_normalize_spot_checked_real_row():
    df = sodir.normalize(_text())
    row = df[df["well_id"] == "sodir:1/2-1"].iloc[0]
    assert row["purpose_raw"] == "WILDCAT"
    assert row["purpose"] == "wildcat"
    assert row["content_raw"] == "OIL"
    assert row["spud_year"] == 1989  # wlbEntryDate 20.03.1989
    assert row["td_m"] == pytest.approx(3574.0)
    # ED50 decimal degrees carried through untransformed (documented)
    assert row["lat"] == pytest.approx(56.887519)
    assert row["lon"] == pytest.approx(2.476583)
    # dscNpdidDiscovery + wlbDiscovery combined into one stable id
    assert row["discovery_id"] == "sodir:43814:1/2-1 Blane"


def test_normalize_covers_all_observed_content_codes():
    df = sodir.normalize(_text())
    assert set(df["content_raw"]) == OBSERVED_CONTENT


def test_purpose_mapping_wildcat_appraisal_ccs_and_blank():
    df = sodir.normalize(_text()).set_index("well_id")
    assert df.loc["sodir:1/2-1", "purpose"] == "wildcat"
    assert df.loc["sodir:1/3-10", "purpose"] == "appraisal"
    # CCS wells are CO2-storage exploration, NOT petroleum wildcats/appraisals
    assert df.loc["sodir:9/6-1", "purpose_raw"] == "WILDCAT-CCS"
    assert df.loc["sodir:9/6-1", "purpose"] == "other"
    assert df.loc["sodir:32/4-4", "purpose_raw"] == "APPRAISAL-CCS"
    assert df.loc["sodir:32/4-4", "purpose"] == "other"
    # the one not-yet-classified wellbore: blank stays verbatim, mapped other
    assert df.loc["sodir:35/11-27 A", "purpose_raw"] == ""
    assert df.loc["sodir:35/11-27 A", "purpose"] == "other"
    assert (df["purpose"] == "wildcat").sum() == 11
    assert (df["purpose"] == "appraisal").sum() == 2
    assert (df["purpose"] == "other").sum() == 5


def test_missing_values_stay_missing_never_invented():
    df = sodir.normalize(_text()).set_index("well_id")
    # 35/11-27 A has blank entry date, TD, content and discovery
    row = df.loc["sodir:35/11-27 A"]
    assert pd.isna(row["spud_year"])
    assert pd.isna(row["td_m"])
    assert row["content_raw"] == ""
    assert pd.isna(row["discovery_id"])
    assert str(df["spud_year"].dtype) == "Int64"
    assert int(df["spud_year"].isna().sum()) == 1
    assert int(df["td_m"].isna().sum()) == 1
    # discovery ids: 7 recorded rows carry one; blanks stay missing, never ""
    assert int(df["discovery_id"].notna().sum()) == 7


def test_padded_varchar_fields_are_stripped():
    # the live export pads varchar fields with trailing spaces; inject the
    # quirk into the recorded rows and assert it never reaches the output
    def pad(header, rows):
        content, purpose = header.index("wlbContent"), header.index("wlbPurpose")
        for row in rows:
            row[content] = row[content].ljust(20)
            row[purpose] = " " + row[purpose] + "  "

    df = sodir.normalize(_mutate(pad))
    assert set(df["content_raw"]) == OBSERVED_CONTENT
    assert set(df["purpose_raw"]) == {"WILDCAT", "APPRAISAL", "WILDCAT-CCS", "APPRAISAL-CCS", ""}


def test_unknown_purpose_raises_never_defaults_to_other():
    text = _text().replace("APPRAISAL-CCS", "DELINEATION-X")
    with pytest.raises(ContractViolation, match="DELINEATION-X"):
        sodir.normalize(text)


def test_drifted_entry_date_format_raises_not_coerced():
    text = _text().replace("20.03.1989", "1989-03-20")
    with pytest.raises(ContractViolation, match="wlbEntryDate"):
        sodir.normalize(text)


def test_unparseable_total_depth_raises_not_guessed():
    text = _text().replace("3574.0", "abc")
    with pytest.raises(ContractViolation, match="wlbTotalDepth"):
        sodir.normalize(text)


def test_zero_data_rows_raises_not_empty_but_fresh():
    header_only = _text().splitlines()[0] + "\r\n"
    with pytest.raises(SourceUnavailable, match="zero data rows"):
        sodir.normalize(header_only)


def test_non_export_body_raises():
    # e.g. an SSRS/HTML error page instead of the report CSV
    with pytest.raises(SourceUnavailable, match="required columns"):
        sodir.normalize("<html>Reporting Services Error</html>")


def test_blank_wellbore_name_pk_raises():
    def blank_pk(header, rows):
        rows[0][header.index("wlbWellboreName")] = ""

    with pytest.raises(ContractViolation, match="wlbWellboreName"):
        sodir.normalize(_mutate(blank_pk))


def test_hard_duplicate_rows_collapse_to_one():
    def duplicate(header, rows):
        rows.append(list(rows[0]))

    df = sodir.normalize(_mutate(duplicate))
    assert len(df) == 18
    assert df["well_id"].is_unique


def test_conflicting_duplicate_pk_fails_contract(tmp_path):
    # same wellbore name, different content: must NOT be silently resolved
    def conflict(header, rows):
        clone = list(rows[0])
        clone[header.index("wlbContent")] = "DRY"
        rows.append(clone)

    frame = sodir.normalize(_mutate(conflict))
    assert len(frame) == 19  # both survive normalize; the contract kills them

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=sodir.SOURCE_ID,
            transform_version=sodir.TRANSFORM_VERSION,
            schema=sodir.SCHEMA,
            fetch=lambda: FetchResult(frame=frame, source_url=sodir.EXPORT_URL),
            table=sodir.TABLE,
            root=tmp_path,
        )
    # nothing persisted, ledger untouched
    assert read_ledger(tmp_path) == []


def test_export_url_is_the_literal_ampersand_ssrs_string():
    # the query is an SSRS report path, not key=value params — a refactor into
    # an httpx params dict would break the endpoint silently
    assert sodir.EXPORT_URL.startswith(
        "https://factpages.sodir.no/public?/Factpages/external/tableview/"
    )
    assert "rs:Format=CSV" in sodir.EXPORT_URL


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = sodir.normalize(_text())

    entry = run_connector(
        source_id=sodir.SOURCE_ID,
        transform_version=sodir.TRANSFORM_VERSION,
        schema=sodir.SCHEMA,
        fetch=lambda: FetchResult(frame=frame, source_url=sodir.EXPORT_URL),
        table=sodir.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 18
    assert entry.table == "sodir_wells"
    assert entry.source_url == sodir.EXPORT_URL
    written = pd.read_parquet(tmp_path / "sodir_wells.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "sodir").all()
    assert (written["transform_version"] == "sodir:1.0.0").all()
    # nullable spud years survive the parquet round-trip as missing, not 0
    assert str(written["spud_year"].dtype) == "Int64"
    assert int(written["spud_year"].isna().sum()) == 1
    assert read_ledger(tmp_path)[0].table == "sodir_wells"
