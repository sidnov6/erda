"""gem_infra offline tests — recorded-real trimmed fixtures, no live network.

Fixtures (see fixtures/README.md):
- gem_infra_listing_sample.xml   — recorded bucket listing, trimmed
- gem_infra_goit_sample.geojson  — 5 verbatim GOIT features
- gem_infra_ggit_lng_sample.geojson — 7 verbatim GGIT-LNG features
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import gem_infra
from erda_ingestion.base import FetchResult, run_connector

FIXTURES = Path(__file__).parent / "fixtures"
LISTING = FIXTURES / "gem_infra_listing_sample.xml"
GOIT = FIXTURES / "gem_infra_goit_sample.geojson"
GGIT = FIXTURES / "gem_infra_ggit_lng_sample.geojson"


def _goit() -> dict:
    return json.loads(GOIT.read_text())


def _ggit() -> dict:
    return json.loads(GGIT.read_text())


# ---------- listing resolution ----------


def test_resolve_picks_latest_release_per_tracker():
    current = gem_infra.resolve_current_files(LISTING.read_text())
    # goit_map_2025-03 AND goit_map_2026-06 are both live in the bucket —
    # the newer YYYY-MM suffix must win.
    assert current["goit"].key == "interim_maps/goit_map_2026-06.geojson"
    assert current["goit"].size == 211894140
    assert current["ggit-lng"].key == "interim_maps/ggit-lng_map_2025-11.geojson"
    assert current["ggit-lng"].size == 196079995
    # other trackers in the bucket (gcpt, goget, folder marker) are ignored
    assert set(current) == {"goit", "ggit-lng"}


def test_resolve_missing_tracker_raises():
    xml = LISTING.read_text().replace("ggit-lng_map_2025-11", "zzz_map_2025-11")
    with pytest.raises(SourceUnavailable, match="ggit-lng"):
        gem_infra.resolve_current_files(xml)


def test_resolve_truncated_listing_raises():
    xml = LISTING.read_text().replace(
        "<IsTruncated>false</IsTruncated>", "<IsTruncated>true</IsTruncated>"
    )
    with pytest.raises(SourceUnavailable, match="truncated"):
        gem_infra.resolve_current_files(xml)


def test_resolve_non_xml_raises():
    with pytest.raises(SourceUnavailable, match="not parseable XML"):
        gem_infra.resolve_current_files("<html>maintenance page</html> oops <")


# ---------- normalize: GOIT (oil pipelines) ----------


def test_normalize_goit_decimates_and_filters():
    df = gem_infra.normalize(_goit(), "goit")
    # fixture: 5 features; the proposed one (P3857) is filtered out
    assert set(df["project_id"]) == {"P0551", "P0544", "P6195", "P2694"}
    assert (df["kind"] == "oil_pipeline").all()
    assert set(df["status"]) == {"operating", "construction"}
    # P0551: 188-vertex LineString → stride-50 samples 0/50/100/150 + final 187
    p0551 = df[df["project_id"] == "P0551"]
    assert len(p0551) == 5
    assert p0551["vertex_idx"].tolist() == [0, 1, 2, 3, 4]
    # P0544: 103 vertices → 0/50/100 + final 102
    assert len(df[df["project_id"] == "P0544"]) == 4
    # P6195: 2 vertices → 0 + final 1; P2694 (NGL, still oil_pipeline): 22 → 0 + 21
    assert len(df[df["project_id"] == "P6195"]) == 2
    assert len(df[df["project_id"] == "P2694"]) == 2


def test_normalize_goit_start_year_missing_stays_missing():
    df = gem_infra.normalize(_goit(), "goit")
    assert df["start_year"].dtype == pd.Int64Dtype()
    by_pid = df.drop_duplicates("project_id").set_index("project_id")["start_year"]
    assert by_pid["P0551"] == 1982
    assert by_pid["P0544"] == 2027
    # empty start-year → pd.NA, never 0 (P6195 and the NGL line P2694)
    assert pd.isna(by_pid["P6195"])
    assert pd.isna(by_pid["P2694"])


def test_normalize_goit_coordinates_are_lat_lon_ordered():
    df = gem_infra.normalize(_goit(), "goit")
    first = df[(df["project_id"] == "P0551") & (df["vertex_idx"] == 0)].iloc[0]
    # East-West Crude Oil Pipeline (Saudi Arabia): lat ~2x, lon ~4x — a
    # [lon, lat] swap would put "lat" near 50 and fail here
    assert 16 < first["lat"] < 33
    assert 34 < first["lon"] < 56
    assert first["country"] == "Saudi Arabia"


# ---------- normalize: GGIT-LNG (gas pipelines + LNG terminals) ----------


def test_normalize_ggit_kinds_and_counts():
    df = gem_infra.normalize(_ggit(), "ggit-lng")
    # kept: P3176 (gas MultiLineString, 147 flat vertices → 0/50/100 + 146),
    # P5315 (2 vertices → 2 rows), Incheon import, Qatar North Field export.
    # dropped: cancelled North Pars terminal, proposed Power of Siberia 2,
    # skipped: Klaipeda blank-facility-type quirk (counted, under tolerance).
    assert len(df) == 4 + 2 + 1 + 1
    kinds = df.groupby("kind").size().to_dict()
    assert kinds == {"gas_pipeline": 6, "lng_import": 1, "lng_export": 1}
    assert "T100000130584" not in set(df["project_id"])  # cancelled → filtered
    assert "P5409" not in set(df["project_id"])  # proposed → filtered
    assert "T100001048134" not in set(df["project_id"])  # blank facility-type → skipped


def test_normalize_ggit_multilinestring_flattens_across_parts():
    df = gem_infra.normalize(_ggit(), "ggit-lng")
    p3176 = df[df["project_id"] == "P3176"]
    assert len(p3176) == 4  # 147 flattened vertices: 0, 50, 100 + final 146
    assert p3176["vertex_idx"].tolist() == [0, 1, 2, 3]


def test_normalize_ggit_terminals_use_latitude_longitude_props():
    df = gem_infra.normalize(_ggit(), "ggit-lng")
    incheon = df[df["project_id"] == "T100000130312"].iloc[0]
    assert incheon["kind"] == "lng_import"
    assert incheon["vertex_idx"] == 0
    assert incheon["lat"] == pytest.approx(37.35124)
    assert incheon["lon"] == pytest.approx(126.602)
    qatar = df[df["project_id"] == "T100000130817"].iloc[0]
    assert qatar["kind"] == "lng_export"
    assert qatar["status"] == "construction"
    assert pd.isna(qatar["start_year"])  # blank on the live feature


def test_normalize_ggit_phased_range_start_year_takes_first_year():
    df = gem_infra.normalize(_ggit(), "ggit-lng")
    p5315 = df[df["project_id"] == "P5315"]
    # live "2013-2017" phased window → earliest in-service year
    assert (p5315["start_year"] == 2013).all()


def test_start_year_unknown_format_raises():
    with pytest.raises(ContractViolation, match="refusing to guess"):
        gem_infra._parse_start_year("mid-2020s", "P9999")


def test_start_year_before_form_is_missing_not_guessed():
    assert gem_infra._parse_start_year("Before 2024", "P4632") is None


def test_normalize_unclassifiable_over_tolerance_raises(monkeypatch):
    monkeypatch.setattr(gem_infra, "UNCLASSIFIABLE_TOLERANCE", 0)
    with pytest.raises(ContractViolation, match="unclassifiable"):
        gem_infra.normalize(_ggit(), "ggit-lng")


# ---------- failure semantics ----------


def test_normalize_rejects_non_feature_collection():
    with pytest.raises(SourceUnavailable, match="not a GeoJSON FeatureCollection"):
        gem_infra.normalize({"error": "AccessDenied"}, "goit")


def test_normalize_rejects_zero_features():
    with pytest.raises(SourceUnavailable, match="zero features"):
        gem_infra.normalize({"type": "FeatureCollection", "features": []}, "goit")


def test_normalize_zero_kept_rows_raises():
    payload = _goit()
    payload["features"] = [
        f for f in payload["features"] if f["properties"]["status"] == "proposed"
    ]
    with pytest.raises(ContractViolation, match="no operating/construction"):
        gem_infra.normalize(payload, "goit")


def test_normalize_unknown_tracker_is_a_programmer_error():
    with pytest.raises(ValueError, match="unknown tracker"):
        gem_infra.normalize(_goit(), "refineries")  # no refineries tracker exists


def test_normalize_point_geometry_in_pipeline_raises():
    payload = _goit()
    payload["features"][0]["geometry"] = {"type": "Point", "coordinates": [4.1, 51.9]}
    with pytest.raises(ContractViolation, match="expected a line"):
        gem_infra.normalize(payload, "goit")


# ---------- full runner path ----------


def _fixture_frame() -> pd.DataFrame:
    return pd.concat(
        [gem_infra.normalize(_goit(), "goit"), gem_infra.normalize(_ggit(), "ggit-lng")],
        ignore_index=True,
    )


def test_runner_full_path_writes_provenance_and_ledger(tmp_path):
    def fake_fetch() -> FetchResult:
        return FetchResult(frame=_fixture_frame(), source_url=gem_infra.LISTING_URL)

    entry = run_connector(
        source_id=gem_infra.SOURCE_ID,
        transform_version=gem_infra.TRANSFORM_VERSION,
        schema=gem_infra.SCHEMA,
        fetch=fake_fetch,
        table=gem_infra.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 21  # 13 goit + 8 ggit-lng
    written = pd.read_parquet(tmp_path / "gem_infra.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "gem_infra").all()
    assert written["start_year"].dtype == pd.Int64Dtype()
    assert read_ledger(tmp_path)[0].table == "gem_infra"


def test_runner_rejects_contract_violation(tmp_path):
    bad = _fixture_frame()
    bad.loc[0, "kind"] = "refinery"  # no refineries tracker exists — not a kind

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=gem_infra.LISTING_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=gem_infra.SOURCE_ID,
            transform_version=gem_infra.TRANSFORM_VERSION,
            schema=gem_infra.SCHEMA,
            fetch=fake_fetch,
            table=gem_infra.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []


def test_duplicate_vertex_key_violates_contract(tmp_path):
    dup = _fixture_frame()
    dup = pd.concat([dup, dup.iloc[[0]]], ignore_index=True)
    dup.loc[len(dup) - 1, "lat"] = 0.0  # same (kind, project_id, vertex_idx), new payload

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=dup, source_url=gem_infra.LISTING_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=gem_infra.SOURCE_ID,
            transform_version=gem_infra.TRANSFORM_VERSION,
            schema=gem_infra.SCHEMA,
            fetch=fake_fetch,
            table=gem_infra.TABLE,
            root=tmp_path,
        )
