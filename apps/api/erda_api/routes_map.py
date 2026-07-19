"""Map data endpoints (§13.4) — compact payloads for the deck.gl hero.

Wells, infrastructure, and protected areas are served as columnar arrays (not
lists of objects) to keep 32k-point payloads small. Everything is cached in
memory per data-root; the snapshot is immutable at serve time (§10.3/§15).

No prospectivity raster is served — the §9.8 falsification gate failed, so the
map carries wells + context only. /api/map/meta states that on the record.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter

from erda_api import data

router = APIRouter(prefix="/api/map")

#: outcome code (industry map convention, §13.1): 2 oil, 1 gas, 3 discovery
#: (phase unrecorded), 0 dry, -1 excluded/no-outcome. Oil vs gas is split from
#: the raw content string ONLY where it cleanly names the phase — the green-oil
#: / red-gas convention experts expect, without fabricating a phase where the
#: source has none (e.g. BOEM's lease-level proxy label, or a dedup cluster
#: whose representative row is a dry sidetrack).
_OIL, _GAS, _DISCOVERY, _DRY, _UNKNOWN = 2, 1, 3, 0, -1


def _outcome_codes(df: pd.DataFrame) -> np.ndarray:
    label = df["label"].to_numpy()
    excluded = df["excluded"].to_numpy()
    content = (
        df["content_raw"].astype(str).str.upper()
        if "content_raw" in df.columns
        else pd.Series([""] * len(df))
    )
    has_oil = content.str.contains("OIL").to_numpy()
    has_gas = content.str.contains("GAS").to_numpy()

    codes = np.full(len(df), _DRY, dtype=int)
    codes[label == 1] = _DISCOVERY  # discovered, phase not cleanly named
    codes[(label == 1) & has_oil] = _OIL
    codes[(label == 1) & has_gas & ~has_oil] = _GAS
    codes[excluded] = _UNKNOWN
    return codes


@lru_cache(maxsize=4)
def _wells_payload(root: str) -> dict:
    df = data.read_table("wells_harmonized")
    if df is None:
        return {"available": False, "reason": "wells_harmonized not in snapshot"}
    df = df.dropna(subset=["lat", "lon", "spud_year"])
    # round coordinates to 4 dp (~11 m) — plenty for a 5 km-grid screening map,
    # and it shrinks the payload; outcome as an int8 code, year as int16.
    # wells_harmonized is the derived label DB (built by ops/build_labels.py),
    # not a connector output, so it carries source_id but not the full
    # provenance quartet — cite the harmonization artifact + contributing sources.
    sources = sorted(df["source_id"].unique().tolist()) if "source_id" in df.columns else []
    return {
        "available": True,
        "n": int(len(df)),
        "lon": [round(float(v), 4) for v in df["lon"]],
        "lat": [round(float(v), 4) for v in df["lat"]],
        "outcome": [int(v) for v in _outcome_codes(df)],
        "spud_year": [int(v) for v in df["spud_year"]],
        "provenance": {
            "source_id": "labels_harmonized",
            "contributing_sources": sources,
            "source_url": "data/parquet/wells_harmonized.parquet (see dataset card)",
        },
        "legend": {"1": "discovery", "0": "dry hole", "-1": "no recorded outcome"},
    }


@router.get("/wells")
def wells() -> dict:
    return _wells_payload(str(data.parquet_root()))


#: keep the map light: sample every Nth pipeline vertex is already done upstream
#: (gem_infra rows are decimated vertices); we further cap to the busiest set.
@lru_cache(maxsize=4)
def _infra_payload(root: str) -> dict:
    df = data.read_table("gem_infra")
    if df is None:
        return {"available": False, "reason": "gem_infra not in snapshot"}
    df = df.dropna(subset=["lat", "lon"])
    pipelines = df[df["kind"].isin(["oil_pipeline", "gas_pipeline"])]
    terminals = df[df["kind"].isin(["lng_import", "lng_export"])]
    return {
        "available": True,
        "pipelines": {
            "lon": [round(float(v), 3) for v in pipelines["lon"]],
            "lat": [round(float(v), 3) for v in pipelines["lat"]],
            "kind": pipelines["kind"].tolist(),
            "n": int(len(pipelines)),
        },
        "terminals": [
            {"lon": round(float(r.lon), 3), "lat": round(float(r.lat), 3),
             "name": r.name, "kind": r.kind}
            for r in terminals.itertuples()
        ],
        "provenance": data.provenance_of(df),
    }


@router.get("/infra")
def infra() -> dict:
    return _infra_payload(str(data.parquet_root()))


#: The map overlay is visual context only; the precise per-block WDPA overlap is
#: computed by the Environment tool at memo time. So we cap to the largest marine
#: areas and simplify to the 0.05° grid resolution — a global overlay under a few
#: MB that stays interactive (< 2 s gate). PROTECTED_MAP_CAP largest by area.
PROTECTED_MAP_CAP = 600
PROTECTED_SIMPLIFY_DEG = 0.1
PROTECTED_COORD_DP = 3  # ~110 m — the overlay is context, not a survey


def _round_coords(obj):
    """Recursively round coordinate floats in a GeoJSON geometry mapping."""
    if isinstance(obj, float):
        return round(obj, PROTECTED_COORD_DP)
    if isinstance(obj, list):
        return [_round_coords(x) for x in obj]
    if isinstance(obj, tuple):
        return [_round_coords(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _round_coords(v) for k, v in obj.items()}
    return obj


@lru_cache(maxsize=4)
def _protected_payload(root: str) -> dict:
    import geopandas as gpd

    path = data.parquet_root() / "wdpa_areas.parquet"
    if not path.exists():
        return {"available": False, "reason": "wdpa_areas not in snapshot"}
    gdf = gpd.read_parquet(path)
    total_marine = int(gdf["marine"].sum()) if "marine" in gdf.columns else len(gdf)
    if "marine" in gdf.columns:
        gdf = gdf[gdf["marine"]].copy()
    gdf = gdf.assign(_area=gdf.geometry.area).nlargest(PROTECTED_MAP_CAP, "_area").copy()
    gdf["geometry"] = gdf.geometry.simplify(PROTECTED_SIMPLIFY_DEG, preserve_topology=True)
    keep = [c for c in ("name", "desig_eng", "iucn_cat", "status_yr", "iso3") if c in gdf.columns]
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    fc = _round_coords(gdf[[*keep, "geometry"]].__geo_interface__)
    return {
        "available": True,
        "n": int(len(gdf)),
        "total_marine": total_marine,
        "note": (
            f"largest {PROTECTED_MAP_CAP} marine protected areas shown for context; "
            "precise per-block overlap is computed at memo time"
        ),
        "geojson": fc,
        "provenance": {"source_id": "wdpa", "source_url": "protectedplanet.net (UNEP-WCMC & IUCN)"},
    }


@router.get("/protected")
def protected() -> dict:
    return _protected_payload(str(data.parquet_root()))


@router.get("/meta")
def meta() -> dict:
    """What the map layers are — and, honestly, what is absent (§9.8)."""
    return {
        "layers": ["wells", "infrastructure", "protected_areas"],
        "prospectivity_raster": {
            "present": False,
            "reason": "§9.8 falsification gate failed — no model raster ships",
            "reference": "/validation → model validation",
        },
        "well_time_range": _wells_time_range(str(data.parquet_root())),
    }


@lru_cache(maxsize=4)
def _wells_time_range(root: str) -> dict:
    df = data.read_table("wells_harmonized")
    if df is None or df["spud_year"].isna().all():
        return {"min": None, "max": None}
    return {"min": int(df["spud_year"].min()), "max": int(df["spud_year"].max())}
