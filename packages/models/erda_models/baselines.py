"""Baselines the prospectivity model must beat (spec §9.6, falsification gate §9.8).

Three skill-free reference strategies:

(a) ``random_baseline`` — seeded uniform noise.
(b) ``DistanceLogitBaseline`` — logistic regression on a single feature,
    distance-to-nearest-discovery-km: the "drill next to old wells" heuristic.
    Beating this under spatial CV is the whole claim; if the model cannot,
    Phase 3 stops honestly (CLAUDE.md rule 7).
(c) ``sediment_threshold_baseline`` — sediment thickness above a fixed cutoff.

Purity contract: no I/O, no network, no unseeded randomness. Callers own all
data loading and leakage control (e.g. distances computed pre-cutoff and outside
the 50 km CV exclusion buffer, §9.4). Degenerate inputs raise ``ValueError`` —
this module never invents numbers (rule 4).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.linear_model import LogisticRegression

__all__ = [
    "DistanceLogitBaseline",
    "random_baseline",
    "sediment_threshold_baseline",
]


def random_baseline(n: int, seed: int) -> NDArray[np.float64]:
    """Baseline (a): ``n`` scores drawn uniform on [0, 1) from a seeded Generator.

    Deterministic: identical ``(n, seed)`` -> identical array.

    Args:
        n: Number of scores to draw (>= 0).
        seed: Seed for ``numpy.random.default_rng``.

    Returns:
        1-D float64 array of length ``n`` with values in [0, 1).

    Raises:
        ValueError: If ``n`` is negative.
    """
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, 1.0, size=n)


def _as_1d_finite(values: ArrayLike, name: str) -> NDArray[np.float64]:
    """Coerce to a 1-D finite float64 array or raise ``ValueError``."""
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(
            f"{name} contains NaN/inf; caller must supply clean leakage-safe distances "
            "— this module never imputes (CLAUDE.md rule 4)"
        )
    return arr


class DistanceLogitBaseline:
    """Baseline (b): logistic regression on distance-to-nearest-discovery alone.

    The "drill next to old wells" opponent of the §9.8 falsification gate.
    Deterministic: fixed ``random_state``, lbfgs solver, single feature.

    The caller supplies leakage-safe distances (computed pre-cutoff, respecting
    the spatial-CV exclusion buffer). A training fold with only one class raises
    ``ValueError`` — the caller skips that fold rather than this module
    inventing a fit.
    """

    def __init__(self, random_state: int = 0, max_iter: int = 1000) -> None:
        self.random_state = random_state
        self.max_iter = max_iter
        self._clf: LogisticRegression | None = None

    def fit(self, train_dist_km: ArrayLike, train_labels: ArrayLike) -> DistanceLogitBaseline:
        """Fit p(discovery) ~ logit(distance_to_nearest_discovery_km).

        Args:
            train_dist_km: 1-D finite distances (km) to nearest prior discovery.
            train_labels: 1-D binary outcomes (1 = discovery, 0 = dry), values in {0, 1}.

        Returns:
            ``self``, fitted.

        Raises:
            ValueError: If arrays are empty, non-1-D, non-finite, mismatched in
                length, labels are not binary, or the fold is degenerate
                (single-class) — caller skips such folds, never invents.
        """
        dist = _as_1d_finite(train_dist_km, "train_dist_km")
        labels = np.asarray(train_labels)
        if labels.ndim != 1:
            raise ValueError(f"train_labels must be 1-D, got shape {labels.shape}")
        if labels.shape[0] != dist.shape[0]:
            raise ValueError(
                f"length mismatch: {dist.shape[0]} distances vs {labels.shape[0]} labels"
            )
        labels = labels.astype(np.int64, casting="unsafe")
        unique = np.unique(labels)
        if not np.isin(unique, (0, 1)).all():
            raise ValueError(f"train_labels must be binary in {{0, 1}}, got values {unique}")
        if unique.size < 2:
            raise ValueError(
                f"degenerate single-class training fold (all labels == {unique[0]}); "
                "caller must skip this fold — refusing to fit"
            )
        clf = LogisticRegression(
            solver="lbfgs", random_state=self.random_state, max_iter=self.max_iter
        )
        clf.fit(dist.reshape(-1, 1), labels)
        self._clf = clf
        return self

    def predict_proba(self, test_dist_km: ArrayLike) -> NDArray[np.float64]:
        """Predict p(discovery) for each test distance.

        Args:
            test_dist_km: 1-D finite distances (km) to nearest prior discovery.

        Returns:
            1-D float64 array of p(discovery), one per input distance.

        Raises:
            RuntimeError: If called before ``fit``.
            ValueError: If distances are empty, non-1-D, or non-finite.
        """
        if self._clf is None:
            raise RuntimeError("DistanceLogitBaseline.predict_proba called before fit")
        dist = _as_1d_finite(test_dist_km, "test_dist_km")
        # classes_ is sorted ([0, 1]); column 1 is p(y == 1) = p(discovery).
        return self._clf.predict_proba(dist.reshape(-1, 1))[:, 1]

    @property
    def coef_km(self) -> float:
        """Fitted logit slope per km (negative when near-old-wells is favourable)."""
        if self._clf is None:
            raise RuntimeError("DistanceLogitBaseline.coef_km accessed before fit")
        return float(self._clf.coef_[0, 0])


def sediment_threshold_baseline(
    sed_thickness_m: ArrayLike, threshold_m: float = 500.0
) -> NDArray[np.float64]:
    """Baseline (c): binary-ish scores from a sediment-thickness threshold rule.

    Score 1.0 where sediment thickness strictly exceeds ``threshold_m``, else 0.0.
    NaN maps to 0.0 by design: no sediment data means no oil claim — absence of
    evidence is scored as no prospect, never imputed (CLAUDE.md rule 4).

    Args:
        sed_thickness_m: Sediment thickness in metres (NaN allowed).
        threshold_m: Cutoff in metres; scores are 1.0 strictly above it.

    Returns:
        float64 array of the same shape with values in {0.0, 1.0}.
    """
    sed = np.asarray(sed_thickness_m, dtype=np.float64)
    # NaN > threshold_m is False, so missing data falls through to 0.0.
    return np.where(sed > threshold_m, 1.0, 0.0)
