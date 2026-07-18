"""Robust z-score normalization (spec §6): global stats persisted with
transform_version so scoring uses EXACTLY the training normalization.

DETERMINISTIC CORE — pure numpy.
"""

from __future__ import annotations

import numpy as np

TRANSFORM_VERSION = "geo_stack:1.0.0"


def robust_stats(data: np.ndarray) -> dict[str, float]:
    """Median + IQR over finite values. Raises on all-NaN — absent is absent."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError("no finite values — cannot compute stats")
    q1, med, q3 = np.percentile(finite, [25.0, 50.0, 75.0])
    return {"median": float(med), "iqr": float(q3 - q1)}


def robust_z(data: np.ndarray, stats: dict[str, float]) -> np.ndarray:
    """(x − median) / IQR. Degenerate IQR (constant channel) raises — a
    constant channel carries no signal and should be caught, not zeroed."""
    if stats["iqr"] <= 0:
        raise ValueError(f"degenerate IQR {stats['iqr']} — constant channel?")
    return (data - stats["median"]) / stats["iqr"]
