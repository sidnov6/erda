from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import ofac_eu
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
SDN_FIXTURE = FIXTURES / "ofac_sdn_sample.csv"
CONS_FIXTURE = FIXTURES / "ofac_cons_prim_sample.csv"
EU_FIXTURE = FIXTURES / "eu_fsf_sample.xml"

#: generationDate of the real EU export the fixture was trimmed from
#: (2026-06-05T15:51:25.849+02:00 → UTC).
EU_GENERATED_AT = pd.Timestamp("2026-06-05T13:51:25.849", tz="UTC")


def _sdn_text() -> str:
    return SDN_FIXTURE.read_bytes().decode("utf-8-sig")


def _ofac_entries() -> pd.DataFrame:
    return pd.concat(
        [
            ofac_eu.read_ofac_csv(_sdn_text()),
            ofac_eu.read_ofac_csv(CONS_FIXTURE.read_bytes().decode("utf-8-sig")),
        ],
        ignore_index=True,
    )


def _eu_xml() -> bytes:
    return EU_FIXTURE.read_bytes()


# ---------------------------------------------------------------- OFAC parsing


def test_read_ofac_csv_parses_headerless_rows_and_skips_dos_eof():
    # both live exports end in a lone 0x1A (DOS EOF) line — kept in the fixture
    df = ofac_eu.read_ofac_csv(_sdn_text())
    assert len(df) == 15
    assert list(df.columns) == ["ent_num", "name", "sdn_type", "programs"]
    assert df.loc[df["ent_num"] == "36", "programs"].item() == "CUBA"


def test_read_ofac_csv_wrong_column_count_raises():
    with pytest.raises(ContractViolation, match="expected 12 columns"):
        ofac_eu.read_ofac_csv('1,"TOO","SHORT"\n')


def test_read_ofac_csv_zero_entries_raises():
    with pytest.raises(SourceUnavailable, match="zero entries"):
        ofac_eu.read_ofac_csv("\x1a")


def test_split_program_tokens():
    assert ofac_eu.split_program_tokens("UKRAINE-EO13661] [RUSSIA-EO14024") == [
        "UKRAINE-EO13661",
        "RUSSIA-EO14024",
    ]
    assert ofac_eu.split_program_tokens("CUBA") == ["CUBA"]


# ------------------------------------------------------------ OFAC derivation


def test_normalize_ofac_maps_country_tokens_and_counts():
    out = ofac_eu.normalize_ofac(_ofac_entries())
    assert (out["list_source"] == "OFAC").all()
    assert out["list_generated_at"].isna().all()  # OFAC exports carry no in-band date
    by_program = out.set_index("program")
    # one SDN row + one "] ["-joined second token + one CONS_PRIM row
    assert by_program.loc["RUSSIA-EO14024", "designation_count"] == 3
    assert by_program.loc["CUBA", "iso3"] == "CUB"
    # Syria derives from the post-revocation authorities present live
    assert by_program.loc["PAARSSR-EO13894", "iso3"] == "SYR"
    assert by_program.loc["HRIT-SY", "iso3"] == "SYR"
    # consolidated (non-SDN) list contributes CMIC / HKAA / SSI rows
    assert by_program.loc["CMIC-EO13959", "iso3"] == "CHN"
    assert by_program.loc["HKAA", "iso3"] == "HKG"
    assert by_program.loc["UKRAINE-EO13662", "iso3"] == "UKR"


def test_normalize_ofac_excludes_thematic_programs():
    out = ofac_eu.normalize_ofac(_ofac_entries())
    # SDGT / FTO / BALKANS / NS-PLC rows are in the fixture but yield no country
    for thematic in ["SDGT", "FTO", "BALKANS", "NS-PLC"]:
        assert thematic not in set(out["program"])
    # Ukraine-named programs map to UKR (jurisdiction), never to RUS
    assert set(out.loc[out["program"].str.startswith("UKRAINE"), "iso3"]) == {"UKR"}


def test_normalize_ofac_unknown_token_raises():
    entries = _ofac_entries()
    entries.loc[0, "programs"] = "GEORGIA-EO99999"
    with pytest.raises(ContractViolation, match="GEORGIA-EO99999"):
        ofac_eu.normalize_ofac(entries)


def test_normalize_ofac_zero_country_rows_raises():
    thematic_only = pd.DataFrame(
        {
            "ent_num": ["2674"],
            "name": ["ABBAS, Abu"],
            "sdn_type": ["individual"],
            "programs": ["SDGT"],
        }
    )
    with pytest.raises(ContractViolation, match="no country-program rows"):
        ofac_eu.normalize_ofac(thematic_only)


# -------------------------------------------------------------- EU derivation


def test_normalize_eu_counts_entities_and_records_generation_date():
    out = ofac_eu.normalize_eu(_eu_xml())
    assert (out["list_source"] == "EU").all()
    # the point-in-time export date is recorded on every EU row (§ staleness)
    assert (out["list_generated_at"] == EU_GENERATED_AT).all()
    by_program = out.set_index("program")
    assert by_program.loc["IRN", "iso3"] == "IRN"
    assert by_program.loc["RUSDA", "iso3"] == "RUS"  # Russia destabilising activities
    assert by_program.loc["SDNZ", "iso3"] == "SDN"  # second Sudan code
    assert by_program.loc["UKR", "iso3"] == "UKR"
    # the fixture's TERR (terrorism) entity is thematic → no row
    assert "TERR" not in set(out["program"])
    # counts are distinct sanctionEntity elements (fixture: one per programme)
    assert (out["designation_count"] == 1).all()


def test_normalize_eu_unknown_programme_raises():
    mutated = _eu_xml().replace(b'programme="TERR"', b'programme="XYZQ"')
    with pytest.raises(ContractViolation, match="XYZQ"):
        ofac_eu.normalize_eu(mutated)


def test_normalize_eu_non_xml_raises():
    with pytest.raises(SourceUnavailable, match="not parseable XML"):
        ofac_eu.normalize_eu(b"<html>403 Forbidden</html")


def test_normalize_eu_wrong_root_raises():
    with pytest.raises(SourceUnavailable, match="expected FSF <export>"):
        ofac_eu.normalize_eu(b'<?xml version="1.0"?><notExport/>')


def test_normalize_eu_zero_entities_raises():
    empty = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<export xmlns="http://eu.europa.ec/fpi/fsd/export" '
        b'generationDate="2026-06-05T15:51:25.849+02:00"/>'
    )
    with pytest.raises(SourceUnavailable, match="zero sanctionEntity"):
        ofac_eu.normalize_eu(empty)


def test_normalize_eu_missing_generation_date_raises():
    mutated = _eu_xml().replace(b"generationDate=", b"someOtherAttr=")
    with pytest.raises(ContractViolation, match="generationDate"):
        ofac_eu.normalize_eu(mutated)


# ------------------------------------------------------------- combined table


def test_normalize_combined_floor_and_sort():
    frame = ofac_eu.normalize(_ofac_entries(), _eu_xml())
    assert list(frame.columns) == [
        "iso3",
        "country_name",
        "program",
        "list_source",
        "designation_count",
        "list_generated_at",
    ]
    # every comprehensively-sanctioned jurisdiction the screen exists for
    assert ofac_eu.COMPREHENSIVE_FLOOR <= set(frame["iso3"])
    assert frame["list_source"].isin(["OFAC", "EU"]).all()
    # deterministic ordering
    assert frame.equals(
        frame.sort_values(["list_source", "iso3", "program"]).reset_index(drop=True)
    )


def test_normalize_floor_violation_raises():
    entries = _ofac_entries()
    entries = entries[entries["programs"] != "CUBA"].reset_index(drop=True)
    # Cuba only ever derives from OFAC (the EU has no Cuba regime) — losing it
    # means the screen's coverage collapsed and must fail loudly
    with pytest.raises(ContractViolation, match="CUB"):
        ofac_eu.normalize(entries, _eu_xml())


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    frame = ofac_eu.normalize(_ofac_entries(), _eu_xml())

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=ofac_eu.SOURCE_URL)

    entry = run_connector(
        source_id=ofac_eu.SOURCE_ID,
        transform_version=ofac_eu.TRANSFORM_VERSION,
        schema=ofac_eu.SCHEMA,
        fetch=fake_fetch,
        table=ofac_eu.TABLE,
        root=tmp_path,
    )
    assert entry.rows == len(frame) == 25
    written = pd.read_parquet(tmp_path / "sanctions_programs.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "ofac_eu").all()
    assert read_ledger(tmp_path)[0].table == "sanctions_programs"


def test_runner_rejects_contract_violation(tmp_path):
    bad = ofac_eu.normalize(_ofac_entries(), _eu_xml())
    bad.loc[0, "iso3"] = "xx"  # not an ISO3 code

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=ofac_eu.SOURCE_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=ofac_eu.SOURCE_ID,
            transform_version=ofac_eu.TRANSFORM_VERSION,
            schema=ofac_eu.SCHEMA,
            fetch=fake_fetch,
            table=ofac_eu.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []


def test_scope_warning_is_prominent():
    # the jurisdiction-vs-entity scope caveat is load-bearing documentation;
    # it must stay in the module docstring where every consumer sees it
    assert "NOT" in ofac_eu.__doc__ and "entity-level compliance" in ofac_eu.__doc__
