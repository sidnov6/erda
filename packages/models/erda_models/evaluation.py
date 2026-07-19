"""Metric suite for the prospectivity engine (spec §9.6, rendered on /validation per §11.2).

Pure functions over ``(y_true, y_score)``. No I/O, no network, no randomness, no
global state — callers own file access and figure rendering. Same inputs give
identical outputs.

Conventions
-----------
- ``y_true`` is binary {0, 1}. ``y_score`` is a probability-like score in which
  higher means more likely positive; the Brier score is only meaningful when
  scores are calibrated probabilities in [0, 1].
- ``metric_suite`` raises ``ValueError`` on single-class ``y_true`` (ranking
  metrics are undefined); the caller reports that fold as skipped.
  ``fold_table`` applies exactly this policy per fold.
- Lift@top-decile tie handling: rows are ordered by descending score using a
  stable sort, so tied scores keep their original array order (earlier index
  wins a top-decile slot). The top decile is the first ``ceil(n / 10)`` rows.
- Reliability bins are uniform on [0, 1], half-open ``[lo, hi)`` with the last
  bin closed at 1.0. Empty bins are absent rows — never interpolated.
- Pooled metrics are computed on the concatenation of out-of-fold scores. This
  is NOT the mean of per-fold metrics: ranking metrics do not average linearly
  across folds, and the two can differ substantially.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from sklearn.metrics import average_precision_score, roc_auc_score

METRIC_KEYS = ("pr_auc", "roc_auc", "brier", "lift_top_decile")

FOLD_TABLE_COLUMNS = (
    "fold",
    "n",
    "base_rate",
    "pr_auc",
    "roc_auc",
    "brier",
    "lift_top_decile",
    "skipped",
)

POOLED_LABEL = "pooled"


def _validate_arrays(y_true: ArrayLike, y_score: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """Coerce to 1-D float arrays and check shape/value invariants.

    Raises ``ValueError`` on: shape mismatch, empty input, non-binary labels,
    or non-finite scores. Does NOT check class balance — see ``metric_suite``.
    """
    yt = np.asarray(y_true, dtype=float).ravel()
    ys = np.asarray(y_score, dtype=float).ravel()
    if yt.shape != ys.shape:
        raise ValueError(f"y_true and y_score length mismatch: {yt.shape[0]} vs {ys.shape[0]}")
    if yt.shape[0] == 0:
        raise ValueError("y_true and y_score are empty")
    if not np.isin(yt, (0.0, 1.0)).all():
        raise ValueError("y_true must contain only 0 and 1")
    if not np.isfinite(ys).all():
        raise ValueError("y_score must be finite (no NaN/inf)")
    return yt, ys


def _lift_top_decile(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Precision in the top ``ceil(n/10)`` scored rows divided by the base rate.

    Ties: stable sort on descending score, so tied rows keep original order.
    """
    n = y_true.shape[0]
    k = math.ceil(n / 10)
    order = np.argsort(-y_score, kind="stable")
    precision_top = float(y_true[order[:k]].mean())
    base_rate = float(y_true.mean())
    return precision_top / base_rate


def metric_suite(y_true: ArrayLike, y_score: ArrayLike) -> dict[str, float]:
    """Compute the §9.6 metric suite over one set of labels and scores.

    Returns ``{pr_auc, roc_auc, brier, lift_top_decile, n, base_rate}`` where
    ``pr_auc`` is average precision. ``brier`` is the mean squared error
    between score and label (meaningful for probabilities in [0, 1]).

    Raises
    ------
    ValueError
        If inputs are malformed (see ``_validate_arrays``) or ``y_true``
        contains a single class — the caller reports that fold as skipped.
    """
    yt, ys = _validate_arrays(y_true, y_score)
    if np.unique(yt).shape[0] < 2:
        raise ValueError(
            "y_true contains a single class; ranking metrics are undefined "
            "(caller should report this fold as skipped)"
        )
    return {
        "pr_auc": float(average_precision_score(yt, ys)),
        "roc_auc": float(roc_auc_score(yt, ys)),
        "brier": float(np.mean((ys - yt) ** 2)),
        "lift_top_decile": _lift_top_decile(yt, ys),
        "n": int(yt.shape[0]),
        "base_rate": float(yt.mean()),
    }


def rank_calibrate_within_fold(fold_ids: ArrayLike, y_score: ArrayLike) -> np.ndarray:
    """Percentile-rank each fold's scores to (0, 1] before they are pooled.

    Pooling raw out-of-fold probabilities from independently-trained per-fold
    models conflates two things: how well each model *ranks* within its fold,
    and the arbitrary *scale* of its score distribution. Ranking metrics like
    PR-AUC are then corrupted by the scale differences. Mapping each fold's
    scores to within-fold percentiles removes the scale, leaving only the
    ranking — which is what the metric is meant to measure.

    This is the §9.8 attempt-2 refinement, pre-stated before the run and applied
    identically to the model and every baseline (so it advantages neither). Ties
    take the average rank (deterministic); output is in (0, 1].

    Raises ``ValueError`` on shape mismatch or a fold with no rows.
    """
    from scipy.stats import rankdata

    fids = np.asarray(fold_ids).ravel()
    ys = np.asarray(y_score, dtype=float).ravel()
    if fids.shape != ys.shape:
        raise ValueError(f"fold_ids and y_score length mismatch: {fids.shape[0]} vs {ys.shape[0]}")
    if fids.shape[0] == 0:
        raise ValueError("fold_ids and y_score are empty")
    out = np.empty_like(ys)
    for f in pd.unique(fids):
        mask = fids == f
        n = int(mask.sum())
        if n == 0:  # pragma: no cover - pd.unique never yields an absent value
            raise ValueError(f"fold {f!r} has no rows")
        out[mask] = rankdata(ys[mask], method="average") / n
    return out


def reliability_bins(y_true: ArrayLike, y_score: ArrayLike, n_bins: int = 10) -> pd.DataFrame:
    """Reliability-diagram table on uniform bins over [0, 1].

    Returns a DataFrame with columns ``[bin_lo, bin_hi, mean_score,
    frac_positive, n]``, one row per NON-empty bin, ordered by ``bin_lo``.
    Empty bins are absent rows, never interpolated. Bins are half-open
    ``[lo, hi)``; the last bin includes 1.0. A score exactly equal to an edge
    lands in the bin whose ``bin_lo`` is that edge.

    Raises ``ValueError`` if ``n_bins < 1``, inputs are malformed, or any
    score lies outside [0, 1]. Single-class ``y_true`` is allowed here.
    """
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins}")
    yt, ys = _validate_arrays(y_true, y_score)
    if (ys < 0.0).any() or (ys > 1.0).any():
        raise ValueError("y_score must lie in [0, 1] for reliability bins")

    # Exact edges i/n_bins; searchsorted keeps edge-valued scores in the bin
    # whose lower edge equals the score (no floor(score*n) float drift).
    edges = np.array([i / n_bins for i in range(n_bins + 1)])
    idx = np.searchsorted(edges, ys, side="right") - 1
    idx = np.minimum(idx, n_bins - 1)

    rows: list[dict[str, float | int]] = []
    for b in np.unique(idx):
        mask = idx == b
        rows.append(
            {
                "bin_lo": float(edges[b]),
                "bin_hi": float(edges[b + 1]),
                "mean_score": float(ys[mask].mean()),
                "frac_positive": float(yt[mask].mean()),
                "n": int(mask.sum()),
            }
        )
    return pd.DataFrame(rows, columns=["bin_lo", "bin_hi", "mean_score", "frac_positive", "n"])


def _fold_arrays(fold: Mapping[str, Any], position: int) -> tuple[Any, np.ndarray, np.ndarray]:
    for key in ("fold", "y_true", "y_score"):
        if key not in fold:
            raise ValueError(f"per_fold[{position}] is missing required key {key!r}")
    yt, ys = _validate_arrays(fold["y_true"], fold["y_score"])
    return fold["fold"], yt, ys


def pooled_metrics(per_fold: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Metric suite on the concatenation of all folds' out-of-fold scores.

    Pooled metrics are computed on concatenated OOF scores and are NOT the
    mean of per-fold metrics. Folds skipped per-fold for being single-class
    still contribute their samples to the pool.
    """
    if len(per_fold) == 0:
        raise ValueError("per_fold is empty")
    parts = [_fold_arrays(fold, i) for i, fold in enumerate(per_fold)]
    yt = np.concatenate([p[1] for p in parts])
    ys = np.concatenate([p[2] for p in parts])
    return metric_suite(yt, ys)


def fold_table(per_fold: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Per-fold metric table plus a final pooled row (spec §11.2).

    Each element of ``per_fold`` is a mapping with keys ``fold`` (label),
    ``y_true`` and ``y_score`` (the fold's out-of-fold arrays). Returns a
    DataFrame with columns ``FOLD_TABLE_COLUMNS``; single-class folds get
    ``skipped=True`` with NaN metrics (but real ``n``/``base_rate``), and
    their samples still enter the pooled row. The last row (``fold ==
    "pooled"``) is ``pooled_metrics`` over the concatenated OOF scores —
    which is NOT the mean of the per-fold rows.
    """
    if len(per_fold) == 0:
        raise ValueError("per_fold is empty")
    rows: list[dict[str, Any]] = []
    for i, fold in enumerate(per_fold):
        label, yt, ys = _fold_arrays(fold, i)
        row: dict[str, Any] = {"fold": label, "n": int(yt.shape[0]), "base_rate": float(yt.mean())}
        if np.unique(yt).shape[0] < 2:
            row.update(dict.fromkeys(METRIC_KEYS, float("nan")))
            row["skipped"] = True
        else:
            metrics = metric_suite(yt, ys)
            row.update({key: metrics[key] for key in METRIC_KEYS})
            row["skipped"] = False
        rows.append(row)

    pooled = pooled_metrics(per_fold)
    rows.append({**{key: pooled[key] for key in ("n", "base_rate", *METRIC_KEYS)},
                 "fold": POOLED_LABEL, "skipped": False})
    return pd.DataFrame(rows, columns=list(FOLD_TABLE_COLUMNS))
