"""Build the §6 raster stack: 14 channels on the 0.05° master grid → data/zarr/stack.zarr.

Every channel carries provenance attrs (source from the registry, retrieved_at
of the raw download, transform_version) plus robust normalization stats — the
stack stores RAW physical values; normalization happens at model time with the
persisted stats (inspectability beats pre-baking).

Usage:
  uv run python ops/build_stack.py --channels grav,grav_grad,...   (default: all base)
  uv run python ops/build_stack.py --channels dist_wells           (needs wells_harmonized)
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

RAW = REPO / "data" / "raw"
STORE = REPO / "data" / "zarr" / "stack.zarr"
TRANSFORM_VERSION = "geo_stack:1.0.0"

#: Crustal-type ordinal classes (ch7): 0 oceanic · 1 transitional · 2 continental.
#: CRUST1.0 addon key names, mapped explicitly — build fails on unmapped codes.
CRUST_CLASS_BY_PREFIX: dict[str, int] = {
    # filled from CNtype1_key.txt on first build; raise lists observed codes
}


def _prov(source_id: str, path: Path) -> dict:
    from erda_contracts.registry import load_registry

    entry = load_registry(REPO / "data" / "curated" / "source_registry.yaml")[source_id]
    retrieved = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    return {
        "source_id": source_id,
        "source_url": entry.base_url,
        "retrieved_at": retrieved,
        "transform_version": TRANSFORM_VERSION,
    }


def _finalize(name: str, data: np.ndarray, prov: dict, units: str, extra: dict | None = None):
    from erda_geo.grid import GridSpec
    from erda_geo.normalize import robust_stats
    from erda_geo.stack import channel_dataarray, write_channel

    spec = GridSpec()
    stats = robust_stats(data)
    da = channel_dataarray(
        data,
        spec,
        name,
        units=units,
        **prov,
        extra_attrs={"norm_median": stats["median"], "norm_iqr": stats["iqr"], **(extra or {})},
    )
    write_channel(STORE, da)
    valid = float(np.isfinite(data).mean())
    print(f"[ok] {name}: valid {valid:.1%}, median {stats['median']:.3g}, iqr {stats['iqr']:.3g}")


def _to_master(lat, lon, data, method: str) -> np.ndarray:
    from erda_geo.grid import GridSpec
    from erda_geo.resample import regrid

    spec = GridSpec()
    return regrid(lat, lon, data, spec.lat_centers(), spec.lon_centers(), method=method)


# ————— channels —————


def build_grav() -> None:
    from erda_geo.grid import GridSpec
    from erda_geo.readers import read_netcdf_grid
    from erda_geo.resample import coarsen_mean

    path = RAW / "grav_33.1.nc"
    lat, lon, data = read_netcdf_grid(path, "z")
    spec = GridSpec()
    if data.shape == (9600, 21600):  # cell-registered 1-arcmin, ±80 lat
        coarse = coarsen_mean(data.astype(np.float32), 3)
        full = np.full(spec.shape, np.nan, dtype=np.float32)
        # ±80° band occupies rows 200..3400 of the 3600-row master grid
        full[200:3400, :] = coarse
    else:  # gridline-registered or other layout — bilinear fallback
        full = _to_master(lat, lon, data, "linear").astype(np.float32)
    _finalize("grav_mgal", full, _prov("grav_sandwell", path), "mGal",
              extra={"note": "marine validity only; land pixels are filler, mask via etopo>0"})


def build_grav_grad() -> None:
    from erda_geo.derive import gradient_magnitude
    from erda_geo.grid import GridSpec
    from erda_geo.stack import open_stack

    spec = GridSpec()
    ds = open_stack(STORE)
    grav = ds["grav_mgal"].values
    grad = gradient_magnitude(grav, spec.lat_centers(), spec.res_deg)
    prov = dict(ds["grav_mgal"].attrs)
    prov = {k: prov[k] for k in ("source_id", "source_url", "retrieved_at", "transform_version")}
    _finalize("grav_gradient_mgal_km", grad.astype(np.float32), prov, "mGal/km",
              extra={"derived_from": "grav_mgal"})


def _wrap_lon_180(lon: np.ndarray, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """0..360 source longitudes → −180..180, columns reordered to ascending."""
    if lon.max() <= 180.0:
        return lon, data
    wrapped = np.mod(lon + 180.0, 360.0) - 180.0
    order = np.argsort(wrapped)
    return wrapped[order], data[:, order]


def build_mag() -> None:
    from erda_geo.readers import read_geotiff_grid

    path = RAW / "EMAG2_V3_UpCont.tif"
    lat, lon, data = read_geotiff_grid(path)
    data[data == 99999.0] = np.nan  # EMAG2 sentinel (registry)
    lon, data = _wrap_lon_180(lon, data)  # tif is 0..360 (observed at build)
    full = _to_master(lat, lon, data, "linear").astype(np.float32)
    _finalize("mag_anomaly_nt", full, _prov("emag2", path), "nT",
              extra={"layer": "UpCont 4km continuation (full coverage variant)"})


def build_sed() -> None:
    from erda_geo.readers import read_netcdf_grid

    path = RAW / "GlobSed-v3.nc"
    lat, lon, data = read_netcdf_grid(path, "z")
    full = _to_master(lat, lon, data, "linear").astype(np.float32)
    _finalize("sed_thickness_m", full, _prov("globsed", path), "m",
              extra={"note": "land NaN; v3 regional-update caveats in registry"})


def build_sed_grad() -> None:
    from erda_geo.derive import gradient_magnitude
    from erda_geo.grid import GridSpec
    from erda_geo.stack import open_stack

    spec = GridSpec()
    ds = open_stack(STORE)
    sed = ds["sed_thickness_m"].values
    grad = gradient_magnitude(sed, spec.lat_centers(), spec.res_deg)
    prov = {k: ds["sed_thickness_m"].attrs[k]
            for k in ("source_id", "source_url", "retrieved_at", "transform_version")}
    _finalize("sed_gradient_m_km", grad.astype(np.float32), prov, "m/km",
              extra={"derived_from": "sed_thickness_m"})


def build_moho() -> None:
    from erda_geo.readers import read_crust1_moho

    path = RAW / "crust1.0.tar.gz"
    lat, lon, moho = read_crust1_moho(path)
    full = _to_master(lat, lon, moho, "linear").astype(np.float32)
    _finalize("moho_depth_km", full, _prov("crust1", path), "km",
              extra={"note": "negative down (boundary elevation)"})


def build_crust_type() -> None:
    from erda_geo.readers import read_crust1_types

    path = RAW / "crust1.0-addon.tar.gz"
    lat, lon, codes = read_crust1_types(path)
    observed = sorted({str(c) for c in codes.ravel()})
    mapping_path = REPO / "data" / "curated" / "crust_type_map.csv"
    if not mapping_path.exists():
        raise SystemExit(
            f"crust_type_map.csv missing. Observed codes ({len(observed)}): {observed}\n"
            "Create the cited mapping (code,class,name) before building ch7."
        )
    mapping = pd.read_csv(mapping_path, dtype=str).set_index("code")["class"].astype(int)
    unmapped = [c for c in observed if c not in mapping.index]
    if unmapped:
        raise SystemExit(f"unmapped crustal type codes: {unmapped}")
    class_grid = np.vectorize(lambda c: mapping[str(c)])(codes).astype(float)
    full = _to_master(lat, lon, class_grid, "nearest").astype(np.float32)
    _finalize("crust_type_class", full, _prov("crust1", path), "class",
              extra={"encoding": "0 oceanic · 1 transitional · 2 continental",
                     "mapping": "data/curated/crust_type_map.csv"})


def build_elevation() -> None:
    from erda_geo.readers import read_netcdf_grid
    from erda_geo.resample import coarsen_mean

    path = RAW / "ETOPO_2022_60s_bed.nc"
    lat, lon, data = read_netcdf_grid(path, "z")
    if data.shape == (10800, 21600):
        if lat[0] < lat[-1]:  # ascending → flip to row-0-north
            data = data[::-1, :]
        full = coarsen_mean(data.astype(np.float32), 3)
    else:
        full = _to_master(lat, lon, data, "linear").astype(np.float32)
    _finalize("elevation_m", full, _prov("etopo2022", path), "m",
              extra={"vertical_datum": "EGM2008; bedrock"})


def build_slope() -> None:
    from erda_geo.derive import slope_deg
    from erda_geo.grid import GridSpec
    from erda_geo.stack import open_stack

    spec = GridSpec()
    ds = open_stack(STORE)
    elev = ds["elevation_m"].values
    out = slope_deg(elev, spec.lat_centers(), spec.res_deg)
    prov = {k: ds["elevation_m"].attrs[k]
            for k in ("source_id", "source_url", "retrieved_at", "transform_version")}
    _finalize("slope_deg", out.astype(np.float32), prov, "deg",
              extra={"derived_from": "elevation_m"})


#: Plausible crustal heat-flow band (mW/m²) — outside it, GHFDB values are
#: dominated by measurement/volcanic artifacts; documented in the card.
HEATFLOW_RANGE = (0.0, 500.0)


def build_heatflow() -> None:
    from erda_geo.derive import idw_grid
    from erda_geo.grid import GridSpec
    from erda_geo.readers import read_ghfdb

    path = RAW / "ghfdb_2024_v2026.03.zip"
    df = read_ghfdb(path)
    df = df[["q", "lat_NS", "long_EW"]].apply(pd.to_numeric, errors="coerce").dropna()
    lo, hi = HEATFLOW_RANGE
    df = df[(df["q"] > lo) & (df["q"] <= hi)]
    df = df[(df["lat_NS"].abs() <= 90) & (df["long_EW"].abs() <= 180)]
    spec = GridSpec()
    field, mean_dist = idw_grid(
        df["lat_NS"].values, df["long_EW"].values, df["q"].values,
        spec.lat_centers(), spec.lon_centers(), k=12, power=2.0,
    )
    prov = _prov("ihfc_heatflow", path)
    _finalize("heat_flow_mw_m2", field.astype(np.float32), prov, "mW/m2",
              extra={"n_points": int(len(df)), "idw_k": 12, "idw_power": 2.0,
                     "q_range_filter": list(HEATFLOW_RANGE)})
    _finalize("heat_flow_obs_dist_km", mean_dist.astype(np.float32), prov, "km",
              extra={"role": "interpolation-uncertainty surface for heat_flow_mw_m2 (§6)"})


def build_dist_shelf() -> None:
    from erda_geo.derive import distance_to_mask_km
    from erda_geo.grid import GridSpec
    from erda_geo.stack import open_stack

    spec = GridSpec()
    ds = open_stack(STORE)
    elev = ds["elevation_m"].values
    shallow = elev > -200.0
    # isobath cells: shallow cells with at least one deep 4-neighbour
    deeper = ~shallow
    neigh = np.zeros_like(shallow)
    neigh[1:, :] |= deeper[:-1, :]
    neigh[:-1, :] |= deeper[1:, :]
    neigh[:, 1:] |= deeper[:, :-1]
    neigh[:, :-1] |= deeper[:, 1:]
    contour = shallow & neigh
    out = distance_to_mask_km(contour, spec.lat_centers(), spec.lon_centers())
    prov = {k: ds["elevation_m"].attrs[k]
            for k in ("source_id", "source_url", "retrieved_at", "transform_version")}
    _finalize("dist_shelf_break_km", out.astype(np.float32), prov, "km",
              extra={"derived_from": "elevation_m", "isobath_m": -200})


def build_provinces() -> None:
    import geopandas as gpd
    from rasterio import features
    from rasterio.transform import from_origin

    from erda_geo.grid import GridSpec
    from erda_geo.stack import open_stack

    path = RAW / "usgs_provinces_wep_prvg.zip"
    extract_dir = RAW / "usgs_provinces"
    if not extract_dir.exists():
        with zipfile.ZipFile(path) as zf:
            zf.extractall(extract_dir)
    shp = next(p for p in extract_dir.rglob("*") if p.suffix.lower() == ".shp")
    gdf = gpd.read_file(shp)
    spec = GridSpec()
    transform = from_origin(-180.0, 90.0, spec.res_deg, spec.res_deg)

    code_grid = features.rasterize(
        ((geom, int(code)) for geom, code in zip(gdf.geometry, gdf["CODE"], strict=True)),
        out_shape=spec.shape, transform=transform, fill=0, dtype="int32",
    ).astype(np.float32)
    type_ord = gdf["TYPE"].fillna("").map({"p": 2.0, "b": 1.0}).fillna(0.0)
    type_grid = features.rasterize(
        ((geom, t) for geom, t in zip(gdf.geometry, type_ord, strict=True)),
        out_shape=spec.shape, transform=transform, fill=0, dtype="float32",
    )
    prov = _prov("usgs_provinces", path)
    _finalize("province_code", code_grid, prov, "code",
              extra={"fill": 0, "n_provinces": int(gdf["CODE"].nunique())})
    _finalize("province_type", type_grid, prov, "ordinal",
              extra={"encoding": "2 priority · 1 boutique · 0 other/none"})

    ds = open_stack(STORE)
    sed = ds["sed_thickness_m"].values
    mask = ((code_grid > 0) & (np.nan_to_num(sed, nan=0.0) > 500.0)).astype(np.float32)
    _finalize("score_mask", mask, prov, "bool",
              extra={"rule": "province_code>0 AND sed_thickness>500m (§6 ch14 masking)"})


BASE_CHANNELS = {
    "grav": build_grav,
    "grav_grad": build_grav_grad,
    "mag": build_mag,
    "sed": build_sed,
    "sed_grad": build_sed_grad,
    "moho": build_moho,
    "crust_type": build_crust_type,
    "elevation": build_elevation,
    "slope": build_slope,
    "heatflow": build_heatflow,
    "dist_shelf": build_dist_shelf,
    "provinces": build_provinces,
}


def build_dist_wells(cutoff_year: int | None = None) -> None:
    """ch12/13: distance to nearest discovery / dry hole (time-aware by cutoff).

    The base stack stores the full-history version; P3's training harness calls
    this with per-fold cutoffs (§6: recomputed per training cutoff, else the
    hindcast leaks).
    """
    from erda_geo.derive import distance_to_points_km
    from erda_geo.grid import GridSpec

    wells_path = REPO / "data" / "parquet" / "wells_harmonized.parquet"
    if not wells_path.exists():
        raise SystemExit("wells_harmonized.parquet missing — run harmonization first")
    wells = pd.read_parquet(wells_path)
    if cutoff_year is not None:
        wells = wells[wells["spud_year"] <= cutoff_year]
    spec = GridSpec()
    suffix = f"_pre{cutoff_year}" if cutoff_year else ""
    prov = {
        "source_id": "labels_harmonized",
        "source_url": "data/parquet/wells_harmonized.parquet",
        "retrieved_at": datetime.fromtimestamp(wells_path.stat().st_mtime, UTC).isoformat(),
        "transform_version": TRANSFORM_VERSION,
    }
    for name, subset in [
        (f"dist_discovery_km{suffix}", wells[wells["label"] == 1]),
        (f"dist_dryhole_km{suffix}", wells[wells["label"] == 0]),
    ]:
        out = distance_to_points_km(
            spec.lat_centers(), spec.lon_centers(), subset["lat"].values, subset["lon"].values
        )
        _finalize(name, out.astype(np.float32), prov, "km",
                  extra={"n_wells": int(len(subset)), "cutoff_year": cutoff_year or "none",
                         "time_aware_rule": "§6 ch12/13 — recompute per training cutoff"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channels", default=",".join(BASE_CHANNELS))
    parser.add_argument("--cutoff-year", type=int, default=None)
    args = parser.parse_args()

    for name in [c.strip() for c in args.channels.split(",") if c.strip()]:
        if name == "dist_wells":
            build_dist_wells(args.cutoff_year)
        elif name in BASE_CHANNELS:
            BASE_CHANNELS[name]()
        else:
            options = sorted(BASE_CHANNELS) + ["dist_wells"]
            raise SystemExit(f"unknown channel {name!r} — options: {options}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
