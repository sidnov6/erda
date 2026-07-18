"""Synthetic tests (spec §11.3) for the leakage defenses — splits and features."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from erda_geo.grid import GridSpec
from erda_models import features, splits

KM_PER_DEG = 111.195


def _wells() -> pd.DataFrame:
    # Province A: 40 wells in a tight line; B: 35 wells 10° away; C: only 5
    rows = []
    for i in range(40):
        rows.append(("A", 60.0 + i * 0.01, 2.0, 1990 + i % 20, i % 2))
    for i in range(35):
        rows.append(("B", 50.0 + i * 0.01, 12.0, 1980 + i % 30, int(i % 3 == 0)))
    for i in range(5):
        rows.append(("C", 40.0, 20.0 + i * 0.01, 2000, 1))
    df = pd.DataFrame(rows, columns=["province_name", "lat", "lon", "spud_year", "label"])
    df["well_id"] = [f"w{i}" for i in range(len(df))]
    df["province_code"] = df["province_name"].map({"A": 1, "B": 2, "C": 3})
    return df


def test_lopo_folds_min_count_and_disjoint():
    wells = _wells()
    folds = splits.lopo_folds(wells, min_wildcats=30)
    assert [f.name for f in folds] == ["A", "B"]  # C has only 5 → never a test fold
    for fold in folds:
        assert set(fold.test_idx).isdisjoint(fold.train_idx)
        # C's wells stay available for training
        assert wells.iloc[fold.train_idx]["province_name"].eq("C").sum() == 5


def test_buffer_actually_drops_nearby_training_wells():
    wells = _wells()
    # plant a "B" well 10 km from an A well — must be dropped from A's fold
    spy = pd.DataFrame(
        [{"province_name": "B", "lat": 60.0 + 10 / KM_PER_DEG, "lon": 2.0,
          "spud_year": 2001, "label": 1, "well_id": "spy", "province_code": 2}]
    )
    wells2 = pd.concat([wells, spy], ignore_index=True)
    fold_a = next(f for f in splits.lopo_folds(wells2, min_wildcats=30) if f.name == "A")
    assert "spy" not in set(wells2.iloc[fold_a.train_idx]["well_id"])
    assert fold_a.n_buffer_dropped >= 1
    # and a well 100 km away survives
    far = pd.DataFrame(
        [{"province_name": "B", "lat": 60.0 + 100 / KM_PER_DEG, "lon": 2.0,
          "spud_year": 2001, "label": 1, "well_id": "far", "province_code": 2}]
    )
    wells3 = pd.concat([wells, far], ignore_index=True)
    fold_a3 = next(f for f in splits.lopo_folds(wells3, min_wildcats=30) if f.name == "A")
    assert "far" in set(wells3.iloc[fold_a3.train_idx]["well_id"])


def test_temporal_split():
    wells = _wells()
    train, test = splits.temporal_split(wells, 2005)
    assert (wells.iloc[train]["spud_year"] <= 2005).all()
    assert (wells.iloc[test]["spud_year"] > 2005).all()
    assert len(train) + len(test) == len(wells)


def _tiny_stack(spec: GridSpec) -> xr.Dataset:
    shape = spec.shape
    rng = np.random.default_rng(7)
    data = {}
    for name in features.STATIC_CHANNELS:
        data[name] = (("lat", "lon"), rng.normal(size=shape))
    ds = xr.Dataset(data, coords={"lat": spec.lat_centers(), "lon": spec.lon_centers()})
    # deterministic elevation: negative everywhere except a known onshore cell
    elev = np.full(shape, -1000.0)
    elev[0, 0] = 100.0
    elev[1, 1] = -200.0
    ds["elevation_m"] = (("lat", "lon"), elev)
    return ds


def test_features_leakage_safety_and_shapes():
    spec = GridSpec(res_deg=10.0)  # tiny 18×36 grid
    ds = _tiny_stack(spec)
    reference = pd.DataFrame(
        {
            "lat": [55.0, 45.0, -5.0],
            "lon": [5.0, 15.0, 100.0],
            "label": [1, 0, 1],
            "province_code": [1, 1, 2],
            "spud_year": [1990, 2000, 2010],
        }
    )
    points = pd.DataFrame(
        {
            "lat": [55.0, -5.0],
            "lon": [5.0, 100.0],
            "province_code": [1, 2],
            "spud_year": [1995, 2015],
        }
    )
    X = features.build_features(points, reference, ds, spec)
    assert list(X.columns) == features.FEATURE_NAMES
    # point 0 sits exactly on a discovery → distance 0
    assert X.loc[0, "dist_discovery_km"] == pytest.approx(0.0, abs=1e-6)
    assert X.loc[0, "dist_dryhole_km"] > 0
    # province success from reference only: prov 1 = 1/2, prov 2 = 1/1
    assert X.loc[0, "province_success_rate"] == pytest.approx(0.5)
    assert X.loc[1, "province_success_rate"] == pytest.approx(1.0)
    # maturity: point 0 spud 1995 — one of two prov-1 reference wells earlier
    assert X.loc[0, "basin_maturity"] == pytest.approx(0.5)
    # removing the far reference discovery changes distances (reference-driven)
    X2 = features.build_features(points, reference.iloc[:2], ds, spec)
    assert X2.loc[1, "dist_discovery_km"] > X.loc[1, "dist_discovery_km"]


def test_features_raise_on_empty_reference_class():
    spec = GridSpec(res_deg=10.0)
    ds = _tiny_stack(spec)
    reference = pd.DataFrame(
        {"lat": [55.0], "lon": [5.0], "label": [1], "province_code": [1], "spud_year": [1990]}
    )
    points = pd.DataFrame({"lat": [55.0], "lon": [5.0], "province_code": [1]})
    with pytest.raises(ValueError, match="empty reference"):
        features.build_features(points, reference, ds, spec)  # no dry holes at all


def test_exclude_self_removes_self_leak():
    spec = GridSpec(res_deg=10.0)
    ds = _tiny_stack(spec)
    reference = pd.DataFrame(
        {
            "lat": [55.0, 45.0, 35.0, 25.0],
            "lon": [5.0, 15.0, 25.0, 35.0],
            "label": [1, 1, 0, 0],
            "province_code": [1, 1, 1, 1],
            "spud_year": [1990, 2000, 2010, 2015],
        }
    )
    # training-side: points ARE the reference
    X = features.build_features(reference, reference, ds, spec, exclude_self=True)
    # discovery well's nearest discovery is the OTHER discovery, not itself
    assert X.loc[0, "dist_discovery_km"] > 1000.0
    # LOO province rate: well 0 (label 1) sees (2−1)/(4−1) = 1/3
    assert X.loc[0, "province_success_rate"] == pytest.approx(1 / 3)
    # well 2 (label 0) sees 2/(4−1) = 2/3
    assert X.loc[2, "province_success_rate"] == pytest.approx(2 / 3)
    # without exclusion the self-leak appears: distance 0
    X_leaky = features.build_features(reference, reference, ds, spec, exclude_self=False)
    assert X_leaky.loc[0, "dist_discovery_km"] == pytest.approx(0.0, abs=1e-6)


def test_water_depth_class_boundaries():
    out = features._water_depth_class(np.array([100.0, 0.0, -200.0, -400.0, -401.0, np.nan]))
    assert out[:5].tolist() == [0.0, 0.0, 1.0, 1.0, 2.0]
    assert np.isnan(out[5])


def test_scoring_points_without_spud_year_get_maturity_one():
    spec = GridSpec(res_deg=10.0)
    ds = _tiny_stack(spec)
    reference = pd.DataFrame(
        {
            "lat": [55.0, 45.0],
            "lon": [5.0, 15.0],
            "label": [1, 0],
            "province_code": [1, 1],
            "spud_year": [1990, 2000],
        }
    )
    points = pd.DataFrame({"lat": [50.0], "lon": [10.0], "province_code": [1]})
    X = features.build_features(points, reference, ds, spec)
    assert X.loc[0, "basin_maturity"] == pytest.approx(1.0)
    # untouched province → maturity 0 (no drilling history)
    points2 = pd.DataFrame({"lat": [50.0], "lon": [10.0], "province_code": [99]})
    X2 = features.build_features(points2, reference, ds, spec)
    assert X2.loc[0, "basin_maturity"] == pytest.approx(0.0)
