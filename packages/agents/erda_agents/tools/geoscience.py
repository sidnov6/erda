"""Geoscience tools (§10.2): offset wells, basin stats, and the honest model
status. All from the harmonized label DB + raster stack — snapshot only."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from erda_agents.tools.base import SnapshotContext
from erda_geo.grid import chord_to_arc_km, unit_vectors

LABEL_SOURCES = ["sodir", "nsta", "nlog", "boem_bsee", "nopims"]


def get_model_score(ctx: SnapshotContext, lat: float, lon: float) -> dict:
    """§9.8 honesty tool: there is NO model score. Returns the gate status and
    whether the location would even be scoreable under the §6 mask, so the
    Geoscience agent can state both plainly."""
    spec = ctx.grid_spec
    row, col = spec.latlon_to_rowcol(np.array([lat]), np.array([lon]))
    mask_val = float(ctx.stack["score_mask"].values[row[0], col[0]])
    return {
        "model_status": "NO MODEL — §9.8 falsification gate failed; no Pg from a model",
        "pg_source": "user-supplied",
        "in_scoreable_mask": bool(mask_val > 0),
        "gate_reference": "packages/models/cards/NEGATIVE_RESULT.md",
        "source_ids": ["model_eval_gbm", "usgs_provinces", "globsed"],
    }


def get_offset_wells(
    ctx: SnapshotContext, lat: float, lon: float, radius_km: float = 100.0
) -> dict:
    wells = ctx.table("wells_harmonized")
    tree = cKDTree(unit_vectors(wells["lat"].values, wells["lon"].values))
    point = unit_vectors(np.array([lat]), np.array([lon]))
    idx = tree.query_ball_point(point[0], r=2.0 * np.sin(radius_km / 6371.0088 / 2.0))
    nearby = wells.iloc[idx]
    labeled = nearby[~nearby["excluded"]]

    chord, _ = tree.query(point, k=min(len(wells), 5))
    nearest = wells.iloc[np.atleast_1d(_).ravel()[: 5]]
    nearest_list = [
        {
            "well_id": r.well_id,
            "outcome_raw": r.content_raw,
            "label": None if r.excluded else int(r.label),
            "spud_year": int(r.spud_year),
            "distance_km": round(float(d), 1),
        }
        for r, d in zip(
            nearest.itertuples(), chord_to_arc_km(np.atleast_1d(chord).ravel()), strict=False
        )
    ]
    present_sources = sorted(nearby["source_id"].unique().tolist()) or LABEL_SOURCES
    return {
        "radius_km": radius_km,
        "n_wells": int(len(nearby)),
        "n_labeled": int(len(labeled)),
        "n_discoveries": int(labeled["label"].sum()) if len(labeled) else 0,
        "offset_success_rate": (
            round(float(labeled["label"].mean()), 3) if len(labeled) else None
        ),
        "nearest_wells": nearest_list,
        "source_ids": present_sources + ["labels_harmonized"],
    }


def get_basin_stats(ctx: SnapshotContext, lat: float, lon: float) -> dict:
    spec = ctx.grid_spec
    row, col = spec.latlon_to_rowcol(np.array([lat]), np.array([lon]))
    province_code = int(ctx.stack["province_code"].values[row[0], col[0]])
    wells = ctx.table("wells_primary")
    in_prov = wells[wells["province_code"] == province_code]
    if len(in_prov):
        name = in_prov["province_name"].iloc[0]
        stats = {
            "province_code": province_code,
            "province_name": name,
            "n_wildcats": int(len(in_prov)),
            "n_discoveries": int(in_prov["label"].sum()),
            "success_rate": round(float(in_prov["label"].mean()), 3),
            "first_spud_year": int(in_prov["spud_year"].min()),
            "last_spud_year": int(in_prov["spud_year"].max()),
            "creaming_note": "count-based maturity — volumes await gated GOGET XLSX",
        }
    else:
        stats = {
            "province_code": province_code,
            "province_name": "(no drilled wildcats in label DB)",
            "n_wildcats": 0,
            "n_discoveries": 0,
            "success_rate": None,
            "first_spud_year": None,
            "last_spud_year": None,
            "creaming_note": "frontier relative to the five-regulator label DB",
        }
    stats["source_ids"] = ["labels_harmonized", "usgs_provinces"]
    return stats
