"""Derived channels (spec §6 ch2/5/9/11/12/13): gradients, slope, distances, IDW.

DETERMINISTIC CORE — pure numpy/scipy. Distances are exact great-circle via
3-D unit vectors + KD-tree (correct at all latitudes and across the antimeridian,
where planar approximations lie).
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from erda_geo.grid import EARTH_RADIUS_KM, chord_to_arc_km, unit_vectors

_KM_PER_DEG = np.pi * EARTH_RADIUS_KM / 180.0  # ≈ 111.195 km per degree of latitude


def gradient_magnitude(data: np.ndarray, lat_centers: np.ndarray, res_deg: float) -> np.ndarray:
    """|∇f| per km, metric-aware: east–west cell size shrinks with cos(lat)."""
    d_lat_km = res_deg * _KM_PER_DEG
    d_lon_km = res_deg * _KM_PER_DEG * np.cos(np.radians(lat_centers))[:, None]
    # lat axis is descending (row 0 = north), so d/dlat flips sign — magnitude unaffected
    df_drow, df_dcol = np.gradient(data)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.hypot(df_drow / d_lat_km, df_dcol / d_lon_km)


def slope_deg(elevation_m: np.ndarray, lat_centers: np.ndarray, res_deg: float) -> np.ndarray:
    """Terrain/seafloor slope in degrees from an elevation grid in meters."""
    grad_m_per_km = gradient_magnitude(elevation_m, lat_centers, res_deg)
    return np.degrees(np.arctan(grad_m_per_km / 1000.0))


def distance_to_points_km(
    lat_grid: np.ndarray, lon_grid: np.ndarray, point_lat: np.ndarray, point_lon: np.ndarray
) -> np.ndarray:
    """Great-circle distance (km) from every grid cell center to the nearest point.

    Serves ch12/13 (distance to pre-cutoff discoveries / dry holes — the caller
    filters points by spud-year cutoff, per the time-aware rule) and analog use.
    Empty point set raises: a missing input is absent data, not infinite distance.
    """
    point_lat = np.atleast_1d(point_lat)
    point_lon = np.atleast_1d(point_lon)
    if len(point_lat) == 0:
        raise ValueError("empty point set — caller must handle absence explicitly")
    tree = cKDTree(unit_vectors(point_lat, point_lon))
    lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)
    cell_vecs = unit_vectors(lat_mesh.ravel(), lon_mesh.ravel())
    chord, _ = tree.query(cell_vecs, k=1)
    return chord_to_arc_km(chord).reshape(len(lat_grid), len(lon_grid))


def distance_to_mask_km(
    mask: np.ndarray, lat_centers: np.ndarray, lon_centers: np.ndarray
) -> np.ndarray:
    """Distance (km) to the nearest True cell — e.g. the 200 m isobath (ch11)."""
    rows, cols = np.nonzero(mask)
    if len(rows) == 0:
        raise ValueError("empty mask — no contour cells found")
    return distance_to_points_km(lat_centers, lon_centers, lat_centers[rows], lon_centers[cols])


def idw_grid(
    point_lat: np.ndarray,
    point_lon: np.ndarray,
    values: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    k: int = 12,
    power: float = 2.0,
    max_dist_km: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Inverse-distance interpolation of sparse points (heat flow, ch10).

    Returns (field, mean_neighbor_distance_km) — the second surface is the
    interpolation-uncertainty flag §6 requires; the UI/model can mask where
    the nearest observations are far. Cells beyond max_dist_km become NaN.
    """
    point_lat = np.atleast_1d(point_lat)
    if len(point_lat) == 0:
        raise ValueError("empty point set")
    k = min(k, len(point_lat))
    tree = cKDTree(unit_vectors(point_lat, np.atleast_1d(point_lon)))
    lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)
    cell_vecs = unit_vectors(lat_mesh.ravel(), lon_mesh.ravel())
    chord, idx = tree.query(cell_vecs, k=k)
    chord = np.atleast_2d(chord.T).T  # (N, k) even when k == 1
    idx = np.atleast_2d(idx.T).T
    dist_km = chord_to_arc_km(chord)

    with np.errstate(divide="ignore"):
        weights = 1.0 / np.maximum(dist_km, 1e-9) ** power
    weights /= weights.sum(axis=1, keepdims=True)
    field = (np.asarray(values, dtype=float)[idx] * weights).sum(axis=1)
    mean_dist = dist_km.mean(axis=1)

    if max_dist_km is not None:
        field = np.where(dist_km.min(axis=1) > max_dist_km, np.nan, field)
    shape = (len(lat_grid), len(lon_grid))
    return field.reshape(shape), mean_dist.reshape(shape)
