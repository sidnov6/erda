import geopandas as gpd
import pandas as pd
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from erda_api.main import app
from erda_api.routes_map import (
    _fields_payload,
    _infra_payload,
    _protected_payload,
    _wells_payload,
    _wells_time_range,
)

client = TestClient(app)


def _seed(tmp_path):
    (tmp_path).mkdir(parents=True, exist_ok=True)
    wells = pd.DataFrame(
        {
            "source_id": ["sodir"] * 3,
            "retrieved_at": pd.to_datetime(["2026-07-19"] * 3, utc=True),
            "source_url": ["https://example.com"] * 3,
            "transform_version": ["v"] * 3,
            "lat": [60.0, 61.0, 62.0],
            "lon": [2.0, 3.0, 4.0],
            "content_raw": ["OIL", "DRY", "GAS"],
            "label": [1, 0, 0],
            "excluded": [False, False, True],
            "spud_year": [1990, 2000, 2010],
        }
    )
    wells.to_parquet(tmp_path / "wells_harmonized.parquet")
    infra = pd.DataFrame(
        {
            "source_id": ["gem_infra"] * 3,
            "retrieved_at": pd.to_datetime(["2026-07-19"] * 3, utc=True),
            "source_url": ["https://example.com"] * 3,
            "transform_version": ["v"] * 3,
            "kind": ["oil_pipeline", "gas_pipeline", "lng_import"],
            "lat": [60.0, 61.0, 62.0],
            "lon": [2.0, 3.0, 4.0],
            "name": ["P1", "P2", "LNG-A"],
        }
    )
    infra.to_parquet(tmp_path / "gem_infra.parquet")
    fields = pd.DataFrame(
        {
            "source_id": ["gem_goget"] * 4,
            "retrieved_at": pd.to_datetime(["2026-07-19"] * 4, utc=True),
            "source_url": ["https://example.com"] * 4,
            "transform_version": ["v"] * 4,
            "name": [
                "Rumaila Oil Field (Iraq)",
                "Groningen Gas Field (Netherlands)",
                "Shaybah Oil and Gas Field",
                "Unnamed Prospect",
            ],
            "status": ["operating", "operating", "operating", "discovered"],
            "lat": [30.0, 53.0, 22.0, -20.0],
            "lon": [47.0, 6.0, 51.0, 15.0],
        }
    )
    fields.to_parquet(tmp_path / "goget_fields.parquet")
    gdf = gpd.GeoDataFrame(
        {"name": ["Reserve A"], "marine": [True]},
        geometry=[Polygon([(1, 59), (5, 59), (5, 63), (1, 63)])],
        crs="EPSG:4326",
    )
    gdf.to_parquet(tmp_path / "wdpa_areas.parquet")


def test_wells_payload_columnar_and_outcome_codes(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    _seed(tmp_path)
    _wells_payload.cache_clear()
    body = client.get("/api/map/wells").json()
    assert body["available"] and body["n"] == 3
    assert body["outcome"] == [2, 0, -1]  # oil / dry / no-outcome(excluded)
    assert len(body["lon"]) == len(body["lat"]) == 3
    assert body["provenance"]["source_id"] == "labels_harmonized"
    assert body["provenance"]["contributing_sources"] == ["sodir"]


def test_infra_and_time_range(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    _seed(tmp_path)
    _infra_payload.cache_clear()
    _wells_time_range.cache_clear()
    infra = client.get("/api/map/infra").json()
    assert infra["pipelines"]["n"] == 2
    assert len(infra["terminals"]) == 1 and infra["terminals"][0]["name"] == "LNG-A"
    meta = client.get("/api/map/meta").json()
    assert meta["prospectivity_raster"]["present"] is False  # §9.8
    assert meta["well_time_range"] == {"min": 1990, "max": 2010}


def test_fields_payload_global_and_phase_parse(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    _seed(tmp_path)
    _fields_payload.cache_clear()
    body = client.get("/api/map/fields").json()
    assert body["available"] and body["n"] == 4
    # phase parsed only where the field name states it; never fabricated
    assert body["phase"] == ["oil", "gas", "both", "und"]
    assert len(body["lon"]) == len(body["lat"]) == 4
    assert body["provenance"]["source_id"] == "gem_goget"
    # the global fields layer is advertised on the map manifest
    assert "global_fields" in client.get("/api/map/meta").json()["layers"]


def test_fields_absent_is_honest(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path / "empty2"))
    (tmp_path / "empty2").mkdir()
    _fields_payload.cache_clear()
    assert client.get("/api/map/fields").json()["available"] is False


def test_protected_geojson(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    _seed(tmp_path)
    _protected_payload.cache_clear()
    body = client.get("/api/map/protected").json()
    assert body["available"] and body["n"] == 1
    assert body["geojson"]["type"] == "FeatureCollection"


def test_wells_absent_is_honest(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    _wells_payload.cache_clear()
    assert client.get("/api/map/wells").json()["available"] is False
