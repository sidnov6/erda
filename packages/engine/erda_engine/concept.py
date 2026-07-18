"""Development concept classifier (spec §10.4) — deterministic thresholds.

water depth ≤ 0 → onshore · ≤ 400 m & host ≤ 50 km → shelf tieback ·
> 400 m & host ≤ 70 km → deepwater tieback · else FPSO standalone.
Depth is meters of water (positive down). Concept maps to a curated cost row
(data/curated/cost_benchmarks.csv) at the Phase-5 tool layer, never here.
DETERMINISTIC CORE — pure.
"""

from __future__ import annotations

import math

CONCEPTS = ["onshore", "shelf_tieback", "deepwater_tieback", "fpso_standalone"]


def classify(water_depth_m: float, host_distance_km: float) -> str:
    if math.isnan(water_depth_m) or math.isnan(host_distance_km):
        raise ValueError("nan input — absent bathymetry/host data must be handled upstream")
    if water_depth_m <= 0.0:
        return "onshore"
    if water_depth_m <= 400.0 and host_distance_km <= 50.0:
        return "shelf_tieback"
    if water_depth_m > 400.0 and host_distance_km <= 70.0:
        return "deepwater_tieback"
    return "fpso_standalone"
