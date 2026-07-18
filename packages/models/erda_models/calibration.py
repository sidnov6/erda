"""Isotonic calibration of prospectivity scores (spec §9.7).

Isotonic regression is fit on OUT-OF-FOLD predictions (never on scores the model
produced for its own training rows) and maps raw model scores to calibrated
probabilities in [0, 1]. The calibrated probability is the Pg that flows into the
economics engine's EMV (spec §10.5):

    EMV = Pg · NPV(success) − (1 − Pg) · dry-hole cost

so a miscalibrated score is not a cosmetic defect — it directly corrupts the
investment decision metric. The reliability curve built from these outputs is
published on /validation.

DETERMINISTIC CORE discipline (spec §0 rule 2 applies in spirit): pure functions,
no I/O, no network, no randomness. Callers own all I/O.
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression


def _as_1d_float(values, name: str) -> np.ndarray:
    """Coerce to a 1-D float array; reject empty or non-finite input."""
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains NaN or infinite values")
    return arr


def _validate_binary_labels(labels: np.ndarray, name: str) -> None:
    classes = np.unique(labels)
    if not np.isin(classes, (0.0, 1.0)).all():
        raise ValueError(f"{name} must be binary 0/1; got values {classes.tolist()}")
    if classes.size < 2:
        raise ValueError(
            f"{name} contains a single class ({int(classes[0])}); "
            "isotonic calibration needs both outcomes"
        )


def fit_isotonic(oof_scores, oof_labels) -> IsotonicRegression:
    """Fit isotonic regression mapping out-of-fold scores → P(discovery).

    Parameters
    ----------
    oof_scores : array-like of shape (n,)
        Raw model scores from spatial-CV out-of-fold predictions (§9.4).
    oof_labels : array-like of shape (n,)
        Binary outcomes (1 = discovery, 0 = dry hole).

    Returns
    -------
    sklearn.isotonic.IsotonicRegression
        Fitted with ``out_of_bounds="clip"``, ``y_min=0``, ``y_max=1`` so that
        scores outside the training range clip to the boundary probabilities.

    Raises
    ------
    ValueError
        On empty/non-finite input, length mismatch, non-binary labels, or
        single-class labels (isotonic fit would be degenerate).
    """
    scores = _as_1d_float(oof_scores, "oof_scores")
    labels = _as_1d_float(oof_labels, "oof_labels")
    if scores.shape != labels.shape:
        raise ValueError(
            f"oof_scores and oof_labels length mismatch: {scores.size} vs {labels.size}"
        )
    _validate_binary_labels(labels, "oof_labels")

    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(scores, labels)
    return model


def apply_calibration(model: IsotonicRegression, scores) -> np.ndarray:
    """Map raw scores through a fitted isotonic model to probabilities in [0, 1].

    Out-of-range scores clip to the boundary probabilities (``out_of_bounds="clip"``).
    The result is the Pg used by the EMV computation (§10.5).
    """
    raw = _as_1d_float(scores, "scores")
    calibrated = np.asarray(model.predict(raw), dtype=float)
    # y_min/y_max already bound the fit; clip guards against interpolation float dust.
    return np.clip(calibrated, 0.0, 1.0)


def _ranking_preserved(raw: np.ndarray, calibrated: np.ndarray, atol: float = 1e-12) -> bool:
    """True iff raw[i] < raw[j] implies calibrated[i] <= calibrated[j] (ties allowed).

    Checked pairwise via groups of tied raw scores: every calibrated value in a
    strictly-higher raw group must be >= every calibrated value in any lower group.
    """
    uniq, inverse = np.unique(raw, return_inverse=True)
    if uniq.size <= 1:
        return True
    group_min = np.full(uniq.size, np.inf)
    group_max = np.full(uniq.size, -np.inf)
    np.minimum.at(group_min, inverse, calibrated)
    np.maximum.at(group_max, inverse, calibrated)
    running_max = np.maximum.accumulate(group_max)
    return bool(np.all(group_min[1:] >= running_max[:-1] - atol))


def calibration_summary(y_true, raw, calibrated) -> dict:
    """Brier scores before/after calibration plus a ranking-preservation check.

    Returns
    -------
    dict
        ``brier_raw`` — mean squared error of raw scores vs outcomes;
        ``brier_calibrated`` — same for calibrated probabilities;
        ``monotone`` — True iff calibration preserved the raw ranking (ties allowed),
        which isotonic regression guarantees by construction.
    """
    labels = _as_1d_float(y_true, "y_true")
    raw_scores = _as_1d_float(raw, "raw")
    cal_scores = _as_1d_float(calibrated, "calibrated")
    if not (labels.shape == raw_scores.shape == cal_scores.shape):
        raise ValueError(
            "y_true, raw, calibrated length mismatch: "
            f"{labels.size}, {raw_scores.size}, {cal_scores.size}"
        )
    return {
        "brier_raw": float(np.mean((raw_scores - labels) ** 2)),
        "brier_calibrated": float(np.mean((cal_scores - labels) ** 2)),
        "monotone": _ranking_preserved(raw_scores, cal_scores),
    }
