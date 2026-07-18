"""gem_goget connector tests — offline, against a recorded-real fixture.

Fixture: tests/fixtures/goget_map_sample.geojson — 11 verbatim features
trimmed from
https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/goget_map_2026-03.geojson
(12,620,640 bytes, 7,673 features) recorded on 2026-07-18. Covers all 10
observed status values plus two empty discovery-year features. No values
were altered.
"""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion.base import run_connector
from erda_labels.sources import gem_goget

FIXTURE = Path(__file__).parent / "fixtures" / "goget_map_sample.geojson"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_normalize_verbatim_fields_and_dtypes():
    df = gem_goget.normalize(_payload())
    assert len(df) == 11
    assert list(df.columns) == [
        "field_id",
        "name",
        "country",
        "status",
        "discovery_year",
        "lat",
        "lon",
    ]
    # PK is source-prefixed and unique
    assert df["field_id"].str.startswith("gem_goget:").all()
    assert df["field_id"].is_unique
    # status is the verbatim observed vocabulary — no re-coding
    assert set(df["status"]) == set(gem_goget.KNOWN_STATUSES)
    # a spot-checked real row, byte-verbatim from the release
    rumaila = df[df["field_id"] == "gem_goget:L100000312002"].iloc[0]
    assert rumaila["name"] == "Rumaila Oil Field (Iraq)"
    assert rumaila["country"] == "Iraq"
    assert rumaila["status"] == "operating"
    assert rumaila["discovery_year"] == 1953
    # GeoJSON [lon, lat] order mapped correctly (Rumaila is in Iraq, lat ~30N)
    assert rumaila["lat"] == pytest.approx(30.5913)
    assert rumaila["lon"] == pytest.approx(47.3528)


def test_empty_discovery_year_is_missing_never_zero():
    df = gem_goget.normalize(_payload())
    assert str(df["discovery_year"].dtype) == "Int64"
    # the two recorded features with discovery-year == "" stay missing
    assert int(df["discovery_year"].isna().sum()) == 2
    assert not (df["discovery_year"].dropna() == 0).any()


def test_unparseable_discovery_year_raises_not_guessed():
    payload = copy.deepcopy(_payload())
    payload["features"][0]["properties"]["discovery-year"] = "circa 1950"
    with pytest.raises(ContractViolation, match="discovery-year"):
        gem_goget.normalize(payload)


def test_non_point_geometry_raises():
    payload = copy.deepcopy(_payload())
    payload["features"][0]["geometry"] = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
    }
    with pytest.raises(ContractViolation, match="expected Point"):
        gem_goget.normalize(payload)


def test_missing_project_id_raises():
    payload = copy.deepcopy(_payload())
    del payload["features"][0]["properties"]["project-id"]
    with pytest.raises(ContractViolation, match="project-id"):
        gem_goget.normalize(payload)


def test_zero_features_raises_not_empty_but_fresh():
    with pytest.raises(SourceUnavailable, match="zero features"):
        gem_goget.normalize({"type": "FeatureCollection", "features": []})


def test_non_feature_collection_payload_raises():
    # e.g. a bucket error document instead of the GeoJSON
    with pytest.raises(SourceUnavailable, match="FeatureCollection"):
        gem_goget.normalize({"error": "NoSuchKey"})


def test_hard_duplicate_features_collapse_to_one_row():
    payload = copy.deepcopy(_payload())
    payload["features"].append(copy.deepcopy(payload["features"][0]))
    df = gem_goget.normalize(payload)
    assert len(df) == 11
    assert df["field_id"].is_unique


def test_conflicting_duplicate_pk_fails_contract(tmp_path):
    # same project-id, different payload: must NOT be silently resolved
    payload = copy.deepcopy(_payload())
    clone = copy.deepcopy(payload["features"][0])
    clone["properties"]["name"] = "A Conflicting Name"
    payload["features"].append(clone)

    def fake_fetch():
        return gem_goget.FetchResult(
            frame=gem_goget.normalize(payload), source_url=gem_goget.DOWNLOAD_URL
        )

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=gem_goget.SOURCE_ID,
            transform_version=gem_goget.TRANSFORM_VERSION,
            schema=gem_goget.SCHEMA,
            fetch=fake_fetch,
            table=gem_goget.TABLE,
            root=tmp_path,
        )
    # nothing persisted, ledger untouched
    assert read_ledger(tmp_path) == []


def test_unknown_status_vocabulary_drift_fails_contract(tmp_path):
    payload = copy.deepcopy(_payload())
    payload["features"][0]["properties"]["status"] = "brand-new-status"

    def fake_fetch():
        return gem_goget.FetchResult(
            frame=gem_goget.normalize(payload), source_url=gem_goget.DOWNLOAD_URL
        )

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=gem_goget.SOURCE_ID,
            transform_version=gem_goget.TRANSFORM_VERSION,
            schema=gem_goget.SCHEMA,
            fetch=fake_fetch,
            table=gem_goget.TABLE,
            root=tmp_path,
        )


def test_load_local_missing_file_raises(tmp_path):
    with pytest.raises(SourceUnavailable, match="missing"):
        gem_goget.load_local(tmp_path / "nope.geojson")


def test_load_local_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.geojson"
    bad.write_text("<html>bucket splash page</html>", encoding="utf-8")
    with pytest.raises(SourceUnavailable, match="not valid JSON"):
        gem_goget.load_local(bad)


def test_runner_full_path_via_load_local(tmp_path):
    entry = run_connector(
        source_id=gem_goget.SOURCE_ID,
        transform_version=gem_goget.TRANSFORM_VERSION,
        schema=gem_goget.SCHEMA,
        fetch=lambda: gem_goget.load_local(FIXTURE),
        table=gem_goget.TABLE,
        root=tmp_path,
    )
    assert entry.rows == 11
    assert entry.table == "goget_fields"
    assert entry.source_url == gem_goget.DOWNLOAD_URL
    written = pd.read_parquet(tmp_path / "goget_fields.parquet")
    # every persisted number carries provenance (§0 rule 5)
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "gem_goget").all()
    assert (written["transform_version"] == "gem_goget:1.0.0").all()
    # nullable years survive the parquet round-trip as missing, not 0
    assert str(written["discovery_year"].dtype) == "Int64"
    assert int(written["discovery_year"].isna().sum()) == 2
    assert read_ledger(tmp_path)[0].table == "goget_fields"
