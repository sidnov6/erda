"""Spatial cross-validation (spec §9.4 — non-negotiable).

Leave-one-province-out over provinces with ≥30 wildcats, PLUS a 50 km
great-circle exclusion buffer: any training well within 50 km of ANY test well
is dropped from that fold's training set. Naive random CV on spatial data is
leakage; this module is the defense, and it is pure and tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from erda_geo.grid import EARTH_RADIUS_KM, unit_vectors

BUFFER_KM = 50.0
MIN_WILDCATS = 30


@dataclass(frozen=True)
class Fold:
    name: str
    test_idx: np.ndarray
    train_idx: np.ndarray
    n_buffer_dropped: int = 0
    meta: dict = field(default_factory=dict)


def _chord_for_km(km: float) -> float:
    """Great-circle km → 3-D chord length on the unit sphere."""
    return 2.0 * np.sin(km / EARTH_RADIUS_KM / 2.0)


def buffer_filter(
    train: pd.DataFrame, test: pd.DataFrame, buffer_km: float = BUFFER_KM
) -> np.ndarray:
    """Boolean mask over `train`: True = keep (farther than buffer from every
    test well). Exact great-circle via unit-sphere KD-tree — no planar lies."""
    if test.empty:
        return np.ones(len(train), dtype=bool)
    tree = cKDTree(unit_vectors(test["lat"].values, test["lon"].values))
    chord, _ = tree.query(unit_vectors(train["lat"].values, train["lon"].values), k=1)
    return chord > _chord_for_km(buffer_km)


def lopo_folds(
    wells: pd.DataFrame,
    min_wildcats: int = MIN_WILDCATS,
    buffer_km: float = BUFFER_KM,
    province_col: str = "province_name",
) -> list[Fold]:
    """Leave-one-province-out folds with the exclusion buffer.

    Provinces below `min_wildcats` (and "(unassigned)") never form a test fold
    but their wells still appear in training sets — small provinces inform,
    they are just never judged in isolation.
    """
    wells = wells.reset_index(drop=True)
    counts = wells[province_col].value_counts()
    eligible = [
        p for p, n in counts.items() if n >= min_wildcats and p != "(unassigned)"
    ]
    folds: list[Fold] = []
    for province in sorted(eligible):
        test_mask = (wells[province_col] == province).values
        test_idx = np.flatnonzero(test_mask)
        train_candidates = wells[~test_mask]
        keep = buffer_filter(train_candidates, wells.iloc[test_idx], buffer_km)
        train_idx = train_candidates.index.values[keep]
        folds.append(
            Fold(
                name=province,
                test_idx=test_idx,
                train_idx=train_idx,
                n_buffer_dropped=int((~keep).sum()),
                meta={
                    "n_test": int(len(test_idx)),
                    "n_train": int(len(train_idx)),
                    "test_base_rate": float(wells.iloc[test_idx]["label"].mean()),
                },
            )
        )
    return folds


def temporal_split(
    wells: pd.DataFrame, cutoff_year: int
) -> tuple[np.ndarray, np.ndarray]:
    """Hindcast split (§9.5): train spud ≤ cutoff, test after. Index arrays."""
    wells = wells.reset_index(drop=True)
    train = np.flatnonzero((wells["spud_year"] <= cutoff_year).values)
    test = np.flatnonzero((wells["spud_year"] > cutoff_year).values)
    return train, test
