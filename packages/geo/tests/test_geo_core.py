"""Synthetic-grid tests (spec §11.3) for the deterministic geo core.

Every expected value is analytically derivable — no golden files, no tolerance
fudging beyond float precision.
"""

import numpy as np
import pytest

from erda_geo import derive, normalize, resample, stack
from erda_geo.grid import EARTH_RADIUS_KM, GridSpec

KM_PER_DEG = np.pi * EARTH_RADIUS_KM / 180.0


def test_grid_spec_shape_and_centers():
    spec = GridSpec()
    assert spec.shape == (3600, 7200)
    lats = spec.lat_centers()
    lons = spec.lon_centers()
    assert lats[0] == pytest.approx(89.975)
    assert lats[-1] == pytest.approx(-89.975)
    assert lons[0] == pytest.approx(-179.975)
    assert lons[-1] == pytest.approx(179.975)


def test_latlon_to_rowcol_roundtrip_and_wrap():
    spec = GridSpec()
    lats = np.array([89.975, 0.0, -89.975])
    lons = np.array([-179.975, 0.0, 179.975])
    row, col = spec.latlon_to_rowcol(lats, lons)
    # floor semantics: a point exactly on a cell edge belongs to the south/east cell
    assert row.tolist() == [0, 1800, 3599]
    assert col.tolist() == [0, 3600, 7199]
    # antimeridian wrap: lon 180 ≡ −180 → column 0
    _, col_wrap = spec.latlon_to_rowcol(np.array([0.0]), np.array([180.0]))
    assert col_wrap.tolist() == [0]


def test_coarsen_mean_exact_and_nan_aware():
    data = np.arange(16, dtype=float).reshape(4, 4)
    out = resample.coarsen_mean(data, 2)
    #  mean of [[0,1],[4,5]] = 2.5 etc.
    assert out.tolist() == [[2.5, 4.5], [10.5, 12.5]]
    data[0, 0] = np.nan
    out = resample.coarsen_mean(data, 2)
    assert out[0, 0] == pytest.approx((1 + 4 + 5) / 3)
    data[:2, :2] = np.nan
    assert np.isnan(resample.coarsen_mean(data, 2)[0, 0])


def test_regrid_bilinear_reproduces_linear_field():
    src_lat = np.array([10.0, 5.0, 0.0])  # descending like real rasters
    src_lon = np.array([0.0, 5.0, 10.0])
    lon_mesh, lat_mesh = np.meshgrid(src_lon, src_lat)
    src = 2.0 * lat_mesh + 3.0 * lon_mesh
    dst_lat = np.array([7.5, 2.5])
    dst_lon = np.array([2.5, 7.5])
    out = resample.regrid(src_lat, src_lon, src, dst_lat, dst_lon)
    expected = 2.0 * np.array([[7.5, 7.5], [2.5, 2.5]]) + 3.0 * np.array([[2.5, 7.5], [2.5, 7.5]])
    np.testing.assert_allclose(out, expected)
    # outside the source extent → NaN, never extrapolated
    outside = resample.regrid(src_lat, src_lon, src, np.array([20.0]), np.array([2.5]))
    assert np.isnan(outside[0, 0])


def test_gradient_plane_and_latitude_scaling():
    res = 1.0
    lat_centers = np.array([60.0, 59.0, 58.0, 57.0])
    lon_centers = np.arange(4, dtype=float)
    lon_mesh, _ = np.meshgrid(lon_centers, lat_centers)
    data = 7.0 * lon_mesh  # varies only east–west: 7 units per degree of lon
    grad = derive.gradient_magnitude(data, lat_centers, res)
    # at lat φ: one degree of lon = KM_PER_DEG·cos(φ) km → |∇| = 7 / that
    for i, lat in enumerate(lat_centers):
        expected = 7.0 / (KM_PER_DEG * np.cos(np.radians(lat)))
        assert grad[i, 1] == pytest.approx(expected, rel=1e-6)


def test_slope_deg_of_known_ramp():
    res = 1.0
    lat_centers = np.array([1.0, 0.0, -1.0])
    lon_centers = np.array([0.0, 1.0, 2.0])
    _, lat_mesh = np.meshgrid(lon_centers, lat_centers)
    elev = 1000.0 * lat_mesh  # 1000 m per degree northward
    out = derive.slope_deg(elev, lat_centers, res)
    expected = np.degrees(np.arctan(1000.0 / (KM_PER_DEG * 1000.0)))
    assert out[1, 1] == pytest.approx(expected, rel=1e-6)


def test_distance_to_points_equator_degree():
    lat_grid = np.array([0.0])
    lon_grid = np.array([0.0, 1.0, 2.0])
    out = derive.distance_to_points_km(lat_grid, lon_grid, np.array([0.0]), np.array([0.0]))
    assert out[0, 0] == pytest.approx(0.0, abs=1e-9)
    assert out[0, 1] == pytest.approx(KM_PER_DEG, rel=1e-6)
    assert out[0, 2] == pytest.approx(2 * KM_PER_DEG, rel=1e-6)
    with pytest.raises(ValueError, match="empty"):
        derive.distance_to_points_km(lat_grid, lon_grid, np.array([]), np.array([]))


def test_distance_crosses_antimeridian_correctly():
    # nearest point to lon 179.5 is at −179.5 — 1° away across the seam, not 359°
    out = derive.distance_to_points_km(
        np.array([0.0]), np.array([179.5]), np.array([0.0]), np.array([-179.5])
    )
    assert out[0, 0] == pytest.approx(KM_PER_DEG, rel=1e-4)


def test_idw_exact_hit_and_uncertainty_surface():
    lat_grid = np.array([0.0, 1.0])
    lon_grid = np.array([0.0, 1.0])
    plat = np.array([0.0, 1.0])
    plon = np.array([0.0, 1.0])
    vals = np.array([10.0, 30.0])
    field, mean_dist = derive.idw_grid(plat, plon, vals, lat_grid, lon_grid, k=1)
    assert field[0, 0] == pytest.approx(10.0)
    assert field[1, 1] == pytest.approx(30.0)
    assert mean_dist[0, 0] == pytest.approx(0.0, abs=1e-6)
    # max_dist mask: everything farther than 10 km from any point → NaN
    field_masked, _ = derive.idw_grid(
        plat, plon, vals, np.array([50.0]), np.array([50.0]), k=1, max_dist_km=10.0
    )
    assert np.isnan(field_masked[0, 0])


def test_robust_z_and_degenerate_guard():
    data = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    stats = normalize.robust_stats(data)
    assert stats["median"] == pytest.approx(3.0)
    z = normalize.robust_z(data, stats)
    assert z[2] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="degenerate"):
        normalize.robust_z(data, {"median": 0.0, "iqr": 0.0})
    with pytest.raises(ValueError, match="finite"):
        normalize.robust_stats(np.array([np.nan, np.nan]))


def test_stack_roundtrip_with_provenance(tmp_path):
    spec = GridSpec(res_deg=30.0)  # tiny 6×12 grid for the round-trip
    data = np.arange(72, dtype=float).reshape(6, 12)
    da = stack.channel_dataarray(
        data,
        spec,
        "test_channel",
        units="mgal",
        source_id="test_src",
        source_url="https://example.com/grid",
        retrieved_at="2026-07-18T00:00:00Z",
        transform_version="geo_stack:1.0.0",
        extra_attrs={"norm_median": 35.5},
    )
    store = tmp_path / "stack.zarr"
    stack.write_channel(store, da)
    ds = stack.open_stack(store)
    np.testing.assert_allclose(ds["test_channel"].values, data)
    assert ds["test_channel"].attrs["source_id"] == "test_src"
    assert ds["test_channel"].attrs["norm_median"] == 35.5
    # shape mismatch raises
    with pytest.raises(ValueError, match="shape"):
        stack.channel_dataarray(
            np.zeros((2, 2)), spec, "bad", units="x", source_id="s",
            source_url="https://example.com", retrieved_at="t", transform_version="v",
        )
