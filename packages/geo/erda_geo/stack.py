"""The Zarr raster cube (spec §6): one group, channels as (lat, lon) arrays,
provenance + normalization stats carried as attrs on every channel.

DETERMINISTIC CORE for transforms; this module's I/O is limited to the local
zarr store the caller names (no network, ever).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from erda_geo.grid import GridSpec


def channel_dataarray(
    data: np.ndarray,
    spec: GridSpec,
    name: str,
    *,
    units: str,
    source_id: str,
    source_url: str,
    retrieved_at: str,
    transform_version: str,
    extra_attrs: dict | None = None,
) -> xr.DataArray:
    """Wrap a channel with its mandatory provenance attrs (§0 rule 5)."""
    if data.shape != spec.shape:
        raise ValueError(f"{name}: shape {data.shape} != grid {spec.shape}")
    attrs = {
        "units": units,
        "source_id": source_id,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "transform_version": transform_version,
        **(extra_attrs or {}),
    }
    return xr.DataArray(
        data.astype(np.float32),
        dims=("lat", "lon"),
        coords={"lat": spec.lat_centers(), "lon": spec.lon_centers()},
        name=name,
        attrs=attrs,
    )


def write_channel(store: Path, da: xr.DataArray) -> None:
    """Add/replace one channel in the stack (mode 'a' keeps existing channels)."""
    da.to_dataset().to_zarr(store, mode="a")


def open_stack(store: Path) -> xr.Dataset:
    return xr.open_zarr(store)
