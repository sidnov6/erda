"""Co-registration onto the master grid (spec §6): continuous → bilinear,
categorical → nearest, finer-to-coarser → NaN-aware block mean.

DETERMINISTIC CORE — pure numpy/scipy, no I/O, no randomness.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import RegularGridInterpolator


def coarsen_mean(data: np.ndarray, factor: int) -> np.ndarray:
    """Exact NaN-aware block mean. Shape must divide evenly by factor."""
    rows, cols = data.shape
    if rows % factor or cols % factor:
        raise ValueError(f"shape {data.shape} not divisible by factor {factor}")
    blocks = data.reshape(rows // factor, factor, cols // factor, factor)
    blocks = blocks.transpose(0, 2, 1, 3).reshape(rows // factor, cols // factor, factor * factor)
    with np.errstate(invalid="ignore"):
        return np.nanmean(blocks, axis=2)


def _interpolator(
    src_lat: np.ndarray, src_lon: np.ndarray, src_data: np.ndarray, method: str
) -> RegularGridInterpolator:
    """Build an interpolator over a regular lat/lon grid (lat may be descending)."""
    lat = np.asarray(src_lat, dtype=float)
    data = np.asarray(src_data, dtype=float)
    if lat[0] > lat[-1]:  # RegularGridInterpolator wants ascending axes
        lat = lat[::-1]
        data = data[::-1, :]
    return RegularGridInterpolator(
        (lat, np.asarray(src_lon, dtype=float)),
        data,
        method=method,
        bounds_error=False,
        fill_value=np.nan,
    )


def regrid(
    src_lat: np.ndarray,
    src_lon: np.ndarray,
    src_data: np.ndarray,
    dst_lat: np.ndarray,
    dst_lon: np.ndarray,
    method: str = "linear",
) -> np.ndarray:
    """Sample a source grid at destination cell centers (linear or nearest).

    Points outside the source extent become NaN — absent, never extrapolated.
    """
    interp = _interpolator(src_lat, src_lon, src_data, method)
    lon_grid, lat_grid = np.meshgrid(dst_lon, dst_lat)
    pts = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])
    return interp(pts).reshape(len(dst_lat), len(dst_lon))
