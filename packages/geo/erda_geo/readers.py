"""Local-file readers for the §6 raster sources.

DETERMINISTIC CORE discipline: file I/O only (no network, ever); every reader
returns plain numpy plus explicit lat/lon axes so downstream transforms stay
pure. Formats follow the live-verified registry notes, not memory.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import xarray as xr


def read_netcdf_grid(path: Path, var: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(lat, lon, data) from a CF-style netCDF grid, lat/lon axis names tolerant."""
    ds = xr.open_dataset(path)
    if var not in ds:
        raise ValueError(f"{path.name}: variable {var!r} not in {list(ds.data_vars)}")
    da = ds[var]
    lat_name = next((n for n in ("lat", "latitude", "y") if n in da.dims), None)
    lon_name = next((n for n in ("lon", "longitude", "x") if n in da.dims), None)
    if lat_name is None or lon_name is None:
        raise ValueError(f"{path.name}: cannot identify lat/lon dims in {da.dims}")
    lat = ds[lat_name].values.astype(float)
    lon = ds[lon_name].values.astype(float)
    data = da.transpose(lat_name, lon_name).values.astype(float)
    ds.close()
    return lat, lon, data


def read_geotiff_grid(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(lat, lon, data) from band 1 of a north-up GeoTIFF; nodata → NaN."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(float)
        if src.nodata is not None:
            data[data == src.nodata] = np.nan
        t = src.transform
        if t.e >= 0:
            raise ValueError(f"{path.name}: expected north-up raster (negative e), got {t.e}")
        lon = t.c + t.a * (np.arange(src.width) + 0.5)
        lat = t.f + t.e * (np.arange(src.height) + 0.5)
    return lat, lon, data


#: CRUST1.0 grid layout (registry): 1°, lon inner loop, start 89.5N/179.5W.
CRUST1_LAT = np.arange(89.5, -90.0, -1.0)
CRUST1_LON = np.arange(-179.5, 180.0, 1.0)


def read_crust1_moho(tar_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moho depth (km, negative down) = 9th boundary in crust1.bnds."""
    with tarfile.open(tar_path, "r:gz") as tar:
        member = tar.extractfile("crust1.bnds")
        if member is None:
            raise ValueError(f"{tar_path.name}: crust1.bnds not found")
        values = np.loadtxt(io.TextIOWrapper(member, encoding="ascii"))
    if values.shape != (64800, 9):
        raise ValueError(f"crust1.bnds: expected (64800, 9), got {values.shape}")
    moho = values[:, 8].reshape(180, 360)
    return CRUST1_LAT.copy(), CRUST1_LON.copy(), moho


def read_crust1_types(addon_tar_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Crustal type codes (str array, 180×360) from the addon CNtype1-1.txt."""
    with tarfile.open(addon_tar_path, "r:gz") as tar:
        member = tar.extractfile("CNtype1-1.txt")
        if member is None:
            raise ValueError(f"{addon_tar_path.name}: CNtype1-1.txt not found")
        lines = [ln.split() for ln in io.TextIOWrapper(member, encoding="ascii") if ln.strip()]
    arr = np.array(lines, dtype=object)
    if arr.shape != (180, 360):
        raise ValueError(f"CNtype1-1.txt: expected (180, 360), got {arr.shape}")
    return CRUST1_LAT.copy(), CRUST1_LON.copy(), arr


def read_ghfdb(zip_path: Path, member_suffix: str = ".txt") -> pd.DataFrame:
    """IHFC GHFDB: TAB-delimited txt inside the GFZ zip, preamble before header.

    Returns the frame with columns as published (q, lat_NS, long_EW, …).
    The header row is located by content ("q" + lat_NS), never by fixed offset —
    the 12-row preamble is a registry observation, not a contract.
    """
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(member_suffix) and "descr" not in n.lower()]
        if not names:
            raise ValueError(f"{zip_path.name}: no {member_suffix} member found")
        raw = zf.read(names[0]).decode("utf-8", errors="replace")
    lines = raw.splitlines()
    header_idx = next(
        (
            i
            for i, ln in enumerate(lines[:50])
            if ln.split("\t")[0].strip() == "q" and "lat_NS" in ln
        ),
        None,
    )
    if header_idx is None:
        raise ValueError(f"{zip_path.name}: header row (q … lat_NS) not found in first 50 lines")
    return pd.read_csv(
        io.StringIO("\n".join(lines[header_idx:])), sep="\t", low_memory=False
    )
