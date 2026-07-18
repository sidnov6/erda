# ERDA Prospectivity Model Card

**Status: NO MODEL SHIPS — falsification gate failed (§9.8).**
Companion write-up: [NEGATIVE_RESULT.md](NEGATIVE_RESULT.md) ·
Evaluation artifacts: `data/parquet/model_eval_gbm.json`, `gbm_oof.parquet` ·
Rendered live on `/validation`.

## What was attempted

A LightGBM classifier over 33 leakage-safe features: 12 physics channels from
the 0.05° raster stack (gravity + gradient, magnetics, sediment thickness +
gradient, Moho, crustal class, bathymetry, slope, heat flow + its uncertainty
surface, shelf-break distance), neighborhood statistics (25/100 km), and
fold-scoped drilling-history features (distance to discoveries/dry holes,
leave-one-out province success, basin maturity). Training data: 17,329
harmonized wildcat decision points (see
`packages/labels/DATASET_CARD.md` — including its BOEM lease-proxy caveat).

## Validation protocol

Leave-one-province-out spatial CV over 14 USGS provinces (≥30 wildcats) with a
50 km great-circle exclusion buffer; every well-derived feature recomputed per
fold from post-buffer training wells only; training-side self-exclusion.
Baselines (§9.6): random, logistic regression on distance-to-nearest-discovery
("drill next to old wells"), sediment-thickness threshold. Gate pre-stated in
`ops/train_gbm.py`: GBM pooled OOF PR-AUC must beat the distance logit on BOTH
the primary and ex-BOEM sets.

## Result

| Set | GBM | Distance baseline | Verdict |
|---|---|---|---|
| primary (17,329) | 0.540 | 0.672 | baseline wins |
| ex_boem (4,885) | 0.416 | 0.414 | tie |

Per-fold wins: 6/14 and 6/11. **No demonstrated skill over the distance
heuristic.** No calibration was fit and no reliability curve is published —
calibrating a model without ranking skill would decorate noise.

## Consequences (per §9.8, accepted by the project owner)

- No prospectivity heatmap, no block scores, no Pg from a model. The MAP panel
  carries wells + context only; the RANK panel states the gate outcome.
- The GBM persists as a **diagnostic**: top mean-|contribution| features are
  dist_discovery_km and province drilling-history features — quantified
  confirmation that in mature basins, drilling history dominates 5 km physics.
- Phase 5 feasibility memos take **user-supplied Pg**; every memo states that
  provenance explicitly.

## Limitations that shaped the outcome

Labels cover five mature offshore jurisdictions — no frontier negatives; the
BOEM proxy (69% of primary) is spatially self-similar and flatters the
distance baseline; 0.05° channels carry basin-scale, not trap-scale, signal.
Legitimate future avenues (each requiring this same pre-stated gate) are
listed in NEGATIVE_RESULT.md.
