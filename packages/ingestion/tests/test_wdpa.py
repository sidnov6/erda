from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import wdpa
from erda_ingestion.base import FetchResult, run_connector

# geopandas/pyogrio resolve from the shared workspace venv (via erda-labels); skip cleanly
# if a stripped env lacks them rather than erroring the whole ingestion suite.
gpd = pytest.importorskip("geopandas")
from shapely.geometry import Polygon  # noqa: E402  (after importorskip)

# Recorded from the WDPA CSV variant
# https://d1gam3xoknrgr2.cloudfront.net/current/WDPA_Jul2026_Public_csv.zip on 2026-07-19
# (member WDPA_Jul2026_Public_csv.csv). 10 real rows: Marine + Coastal + Terrestrial,
# a STATUS_YR=0 row, a transboundary MOZ;ZAF row, and the Established/Inscribed statuses.
CSV_FIXTURE = Path(__file__).parent / "fixtures" / "wdpa_marine_csv_excerpt.csv"


def _raw_csv() -> pd.DataFrame:
    # dtype=str + keep_default_na=False so STATUS_YR "0" stays a string, not NaN.
    return pd.read_csv(CSV_FIXTURE, dtype=str, keep_default_na=False)


def _jagged_square(x0: float, y0: float, size: float, n_per_edge: int) -> Polygon:
    """A square with many redundant collinear vertices — SYNTHETIC geometry.

    Douglas-Peucker at any positive tolerance collapses the collinear points, so
    simplify() must cut the vertex count to the 5 corners.
    """
    pts: list[tuple[float, float]] = []
    corners = [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)]
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1], strict=True):
        for i in range(n_per_edge):
            t = i / n_per_edge
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    pts.append(corners[0])
    return Polygon(pts)


def _synthetic_gdf() -> gpd.GeoDataFrame:
    """SYNTHETIC (spec §11.3) tiny WDPA-shaped GeoDataFrame: 1 Marine, 1 Coastal, 1
    Terrestrial. The terrestrial row must be filtered out; the kept polygons carry many
    collinear vertices to exercise simplify()."""
    rows = [
        ("100", "Reef MPA", "Marine Protected Area", "Ia", "Designated", 1990, "AAA", "Marine"),
        ("200", "Bay Park", "National Park", "II", "Established", 0, "BBB", "Coastal"),
        ("300", "Inland NR", "Nature Reserve", "IV", "Designated", 2001, "CCC", "Terrestrial"),
    ]
    geoms = [
        _jagged_square(0.0, 0.0, 10.0, 25),
        _jagged_square(20.0, 0.0, 10.0, 25),
        _jagged_square(40.0, 0.0, 10.0, 25),
    ]
    cols = ["SITE_ID", "NAME", "DESIG_ENG", "IUCN_CAT", "STATUS", "STATUS_YR", "ISO3", "REALM"]
    df = pd.DataFrame(rows, columns=cols)
    return gpd.GeoDataFrame(df, geometry=geoms, crs="EPSG:4326")


# ————— normalize: CSV path (no geometry) —————


def test_normalize_csv_filters_terrestrial_and_maps_columns():
    out = wdpa.normalize(_raw_csv())
    # 10 rows in, 2 Terrestrial dropped
    assert len(out) == 8
    assert "geometry" not in out.columns
    assert list(out.columns) == [
        "site_id", "name", "desig_eng", "iucn_cat", "status", "status_yr", "iso3", "marine",
    ]
    # terrestrial SITE_IDs (Laguna 3, Formosa 4) never survive
    assert {"3", "4"}.isdisjoint(set(out["site_id"]))


def test_normalize_csv_marine_bool_distinguishes_marine_from_coastal():
    out = wdpa.normalize(_raw_csv()).set_index("site_id")["marine"]
    assert out["1"]  # Diamond Reef — REALM Marine
    assert out["12804"]  # Aleipata MPA — Marine
    assert not out["27"]  # Folkstone — REALM Coastal
    assert not out["198302"]  # iSimangaliso — Coastal


def test_normalize_status_year_zero_becomes_na_not_zero():
    out = wdpa.normalize(_raw_csv()).set_index("site_id")["status_yr"]
    # Langue de Barbarie (869) has STATUS_YR 0 upstream → missing, never 0 or 1970
    assert pd.isna(out["869"])
    assert out["1"] == 1973


def test_normalize_preserves_transboundary_iso3():
    out = wdpa.normalize(_raw_csv()).set_index("site_id")["iso3"]
    assert out["198302"] == "MOZ;ZAF"


def test_normalize_status_vocabulary_within_known_set():
    out = wdpa.normalize(_raw_csv())
    assert set(out["status"]) <= set(wdpa.KNOWN_STATUSES)


def test_normalize_zero_marine_rows_raises():
    raw = _raw_csv()
    terrestrial_only = raw[raw["REALM"] == "Terrestrial"]
    with pytest.raises(SourceUnavailable, match="no Marine/Coastal"):
        wdpa.normalize(terrestrial_only)


def test_normalize_missing_column_raises_contract_violation():
    raw = _raw_csv().drop(columns=["REALM"])
    with pytest.raises(ContractViolation, match="missing columns"):
        wdpa.normalize(raw)


# ————— normalize: GDB path (GeoDataFrame — filter + simplify) —————


def test_normalize_geo_filters_and_simplifies_keeping_geometry():
    raw = _synthetic_gdf()
    before = int(raw.geometry.iloc[0].exterior.coords.__len__())
    out = wdpa.normalize(raw)
    assert isinstance(out, gpd.GeoDataFrame)
    assert out.crs == raw.crs
    assert len(out) == 2  # terrestrial dropped
    # collinear vertices collapse to the square's 5 corners
    after = int(out.geometry.iloc[0].exterior.coords.__len__())
    assert after < before
    assert after == 5
    assert not out.geometry.is_empty.any()


# ————— write path: GeoParquet round-trip + run_connector for the attribute table —————


def test_write_geoparquet_roundtrips_geometry(tmp_path):
    out = wdpa.normalize(_synthetic_gdf())
    path = wdpa.write_geoparquet(out, tmp_path / "wdpa_areas.parquet")
    back = gpd.read_parquet(path)
    assert isinstance(back, gpd.GeoDataFrame)
    assert len(back) == 2
    assert back.geometry.geom_type.eq("Polygon").all()
    assert back.crs == out.crs


def test_run_connector_writes_attributes_with_provenance_and_ledger(tmp_path):
    attributes = wdpa.to_attribute_frame(wdpa.normalize(_synthetic_gdf()))

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=attributes, source_url=wdpa.bulk_url("Jul2026"))

    entry = run_connector(
        source_id=wdpa.SOURCE_ID,
        transform_version=wdpa.TRANSFORM_VERSION,
        schema=wdpa.SCHEMA,
        fetch=fake_fetch,
        table=wdpa.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 2
    assert entry.table == "wdpa_attributes"
    written = pd.read_parquet(tmp_path / "wdpa_attributes.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "wdpa").all()
    assert read_ledger(tmp_path)[0].table == "wdpa_attributes"


def test_run_connector_rejects_unknown_status(tmp_path):
    attributes = wdpa.to_attribute_frame(wdpa.normalize(_synthetic_gdf()))
    attributes.loc[0, "status"] = "Bogus"  # not in KNOWN_STATUSES

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=attributes, source_url=wdpa.bulk_url("Jul2026"))

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=wdpa.SOURCE_ID,
            transform_version=wdpa.TRANSFORM_VERSION,
            schema=wdpa.SCHEMA,
            fetch=fake_fetch,
            table=wdpa.TABLE,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []  # nothing persisted


# ————— URL / month-token rotation —————


def test_month_token_and_candidate_rotation():
    assert wdpa._month_token(date(2026, 7, 19)) == "Jul2026"
    # current then previous month — only the live release is served upstream
    assert wdpa._candidate_tokens(date(2026, 7, 19)) == ["Jul2026", "Jun2026"]
    assert wdpa._candidate_tokens(date(2026, 1, 15)) == ["Jan2026", "Dec2025"]
    assert wdpa.bulk_url("Jul2026").endswith("/current/WDPA_Jul2026_Public.zip")
