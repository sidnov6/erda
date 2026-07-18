"""Leakage-safe GBM features (spec §9.2).

THE RULE: every feature derived from wells — distances to discoveries/dry
holes, province historical success, basin maturity — is computed ONLY from the
`reference` well set the caller passes (a fold's post-buffer training wells, or
the pre-cutoff wells for the hindcast). Passing all wells here is how leakage
happens; the split harness never does.

Static stack channels are fold-independent physics — safe everywhere.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree

from erda_geo.grid import GridSpec, chord_to_arc_km, unit_vectors

#: The 12 physics channels (§6 ch1–11 + 14 family) — fold-independent.
STATIC_CHANNELS = [
    "grav_mgal",
    "grav_gradient_mgal_km",
    "mag_anomaly_nt",
    "sed_thickness_m",
    "sed_gradient_m_km",
    "moho_depth_km",
    "crust_type_class",
    "elevation_m",
    "slope_deg",
    "heat_flow_mw_m2",
    "heat_flow_obs_dist_km",
    "dist_shelf_break_km",
]

#: Channels that also get neighborhood mean/std (25 km ≈ 5 cells, 100 km ≈ 18).
NEIGHBORHOOD_CHANNELS = ["grav_mgal", "mag_anomaly_nt", "sed_thickness_m", "elevation_m"]
NEIGHBORHOOD_RADII_CELLS = {"25km": 5, "100km": 18}


def _point_values(ds: xr.Dataset, spec: GridSpec, rows: np.ndarray, cols: np.ndarray) -> dict:
    out = {}
    for name in STATIC_CHANNELS:
        out[name] = ds[name].values[rows, cols]
    return out


def _neighborhood_stats(
    ds: xr.Dataset, rows: np.ndarray, cols: np.ndarray
) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for name in NEIGHBORHOOD_CHANNELS:
        grid = ds[name].values
        n_rows, n_cols = grid.shape
        for tag, r in NEIGHBORHOOD_RADII_CELLS.items():
            means = np.empty(len(rows))
            stds = np.empty(len(rows))
            for i, (rr, cc) in enumerate(zip(rows, cols, strict=True)):
                r0, r1 = max(0, rr - r), min(n_rows, rr + r + 1)
                # columns wrap the antimeridian
                cols_idx = np.arange(cc - r, cc + r + 1) % n_cols
                window = grid[r0:r1][:, cols_idx]
                finite = window[np.isfinite(window)]
                means[i] = finite.mean() if finite.size else np.nan
                stds[i] = finite.std() if finite.size else np.nan
            out[f"{name}_mean_{tag}"] = means
            out[f"{name}_std_{tag}"] = stds
    return out


#: Chord below this = "the same well" (≈ 6 cm) for self-exclusion purposes.
_SELF_EPS = 1e-8


def _distance_km(
    points: pd.DataFrame, reference: pd.DataFrame, exclude_self: bool = False
) -> np.ndarray:
    """Distance to nearest reference well; exclude_self drops exact self-matches
    (training features: a discovery 0 km from itself is a leak)."""
    if reference.empty:
        raise ValueError("empty reference set — a fold with no wells cannot make features")
    tree = cKDTree(unit_vectors(reference["lat"].values, reference["lon"].values))
    pts = unit_vectors(points["lat"].values, points["lon"].values)
    if not exclude_self:
        chord, _ = tree.query(pts, k=1)
        return chord_to_arc_km(chord)
    k = min(2, len(reference))
    chord, _ = tree.query(pts, k=k)
    chord = np.atleast_2d(chord.T).T
    first = chord[:, 0]
    if k == 1:
        if (first < _SELF_EPS).any():
            raise ValueError("exclude_self with a single-well reference leaves no neighbor")
        return chord_to_arc_km(first)
    out = np.where(first < _SELF_EPS, chord[:, 1], first)
    return chord_to_arc_km(out)


def _water_depth_class(elevation_m: np.ndarray) -> np.ndarray:
    """§10.4 boundaries: 0 onshore (≥0 m) · 1 shelf (> −400 m) · 2 deepwater."""
    out = np.full(len(elevation_m), np.nan)
    finite = np.isfinite(elevation_m)
    out[finite & (elevation_m >= 0)] = 0.0
    out[finite & (elevation_m < 0) & (elevation_m >= -400)] = 1.0
    out[finite & (elevation_m < -400)] = 2.0
    return out


def _province_success(
    points: pd.DataFrame, reference: pd.DataFrame, exclude_self: bool = False
) -> np.ndarray:
    """Historical success rate of the point's province, from reference wells
    ONLY. Provinces absent from the reference fall back to the global reference
    rate (documented: an uninformative prior, never an invented signal).
    exclude_self (training rows that are themselves reference wells): the
    point's own label leaves its province rate — leave-one-out."""
    grouped = reference.groupby("province_code")["label"].agg(["sum", "count"])
    global_rate = float(reference["label"].mean())
    sums = points["province_code"].map(grouped["sum"])
    counts = points["province_code"].map(grouped["count"])
    if exclude_self:
        own = points["label"].values
        sums = sums - own
        counts = counts - 1
    with np.errstate(invalid="ignore", divide="ignore"):
        rates = sums / counts
    return rates.fillna(global_rate).values


def _basin_maturity(points: pd.DataFrame, reference: pd.DataFrame) -> np.ndarray:
    """Position on the province's drilling history (creaming-curve x-axis,
    §9.2): fraction of reference wells in the same province spud strictly
    before the point's spud_year. Scoring rows without spud_year get 1.0 —
    'now', after all reference drilling."""
    out = np.empty(len(points))
    by_prov = {p: g["spud_year"].values for p, g in reference.groupby("province_code")}
    years = points.get("spud_year")
    for i, (prov, _) in enumerate(zip(points["province_code"].values, out, strict=True)):
        ref_years = by_prov.get(prov)
        if ref_years is None or len(ref_years) == 0:
            out[i] = 0.0  # untouched province: no drilling history at all
            continue
        if years is None or pd.isna(years.iloc[i]):
            out[i] = 1.0
        else:
            out[i] = float((ref_years < years.iloc[i]).mean())
    return out


def build_static_features(
    points: pd.DataFrame, ds: xr.Dataset, spec: GridSpec | None = None
) -> pd.DataFrame:
    """Fold-independent physics features — compute ONCE for a well set."""
    spec = spec or GridSpec()
    rows, cols = spec.latlon_to_rowcol(points["lat"].values, points["lon"].values)
    feats: dict[str, np.ndarray] = {}
    feats.update(_point_values(ds, spec, rows, cols))
    feats.update(_neighborhood_stats(ds, rows, cols))
    feats["water_depth_class"] = _water_depth_class(feats["elevation_m"])
    return pd.DataFrame(feats, index=points.index)


def build_reference_features(
    points: pd.DataFrame, reference: pd.DataFrame, exclude_self: bool = False
) -> pd.DataFrame:
    """Well-derived features — from `reference` ONLY (the leakage boundary).

    exclude_self=True when `points` rows are themselves in `reference`
    (training-side features): self-distances and own-label province rates are
    leaks and are removed.
    """
    discoveries = reference[reference["label"] == 1]
    dry = reference[reference["label"] == 0]
    feats = {
        "dist_discovery_km": _distance_km(points, discoveries, exclude_self=exclude_self),
        "dist_dryhole_km": _distance_km(points, dry, exclude_self=exclude_self),
        "province_success_rate": _province_success(points, reference, exclude_self=exclude_self),
        "basin_maturity": _basin_maturity(points, reference),
    }
    return pd.DataFrame(feats, index=points.index)


def build_features(
    points: pd.DataFrame,
    reference: pd.DataFrame,
    ds: xr.Dataset,
    spec: GridSpec | None = None,
    exclude_self: bool = False,
    static: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Full feature matrix; pass a precomputed `static` frame to skip re-reading
    the stack (the CV runner computes it once for all wells)."""
    if static is None:
        static = build_static_features(points, ds, spec)
    ref_feats = build_reference_features(points, reference, exclude_self=exclude_self)
    out = pd.concat([static, ref_feats], axis=1)
    return out[FEATURE_NAMES]


FEATURE_NAMES: list[str] = (
    STATIC_CHANNELS
    + [
        f"{name}_{stat}_{tag}"
        for name in NEIGHBORHOOD_CHANNELS
        for tag in NEIGHBORHOOD_RADII_CELLS
        for stat in ("mean", "std")
    ]
    + [
        "dist_discovery_km",
        "dist_dryhole_km",
        "water_depth_class",
        "province_success_rate",
        "basin_maturity",
    ]
)
