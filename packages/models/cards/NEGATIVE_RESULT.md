# Phase 3 Falsification Gate — Negative Result (§9.8)

**Date:** 2026-07-18 (attempt 1) · 2026-07-19 (attempt 2) · **Verdict: GATE FAILED
(both attempts)** · Full artifacts: `data/parquet/model_eval_gbm.json`,
`gbm_oof.parquet`

> **Two attempts, one honest conclusion.** Attempt 1 used raw pooled PR-AUC and
> failed decisively. Attempt 2 applied a pre-stated metric refinement
> (within-fold rank-calibrated pooling, fair to model and baseline alike); it
> materially improved the GBM and flipped the clean subset to a win, but the
> primary set still favors the baseline. The bar was fixed before each run and
> never moved. No prospectivity heatmap ships.

## The pre-stated bar

Defined in `ops/train_gbm.py` *before* the run: pooled out-of-fold PR-AUC of
the GBM must exceed the distance-to-nearest-discovery logistic baseline
("drill next to old wells") on BOTH the primary set and the true-outcome
`ex_boem` subset, under leave-one-province-out spatial CV with a 50 km
exclusion buffer.

## The measurement

| Set | n | GBM PR-AUC | Distance-logit PR-AUC | Verdict |
|---|---|---|---|---|
| primary (14 folds) | 17,329 | 0.540 | **0.672** | baseline wins decisively |
| ex_boem (11 folds) | 4,885 | 0.416 | 0.414 | statistical tie |

Per-fold: the GBM wins 6/14 primary folds and 6/11 ex-BOEM folds — coin-flip
territory. The 33-feature model (12 physics channels + neighborhood stats +
leakage-safe drilling-history features) demonstrated **no skill over the
distance heuristic** under spatial cross-validation.

## Attempt 2 — within-fold calibrated pooling (2026-07-19)

Diagnosis item 3 below flagged that pooling *raw* probabilities from 14
independently-trained fold-models conflates ranking quality with per-fold
score-scale, and named "per-fold calibrated pooling defined *before* the next
run" as a legitimate refinement. Pre-stated here and run: rank-normalize each
model's out-of-fold scores to within-fold percentiles before pooling, applied
**identically to the GBM and every baseline** (so it advantages neither). Same
metric (PR-AUC), same comparison (vs distance logit), same CV (LOPO + 50 km
buffer), same both-sets rule.

| Set | GBM (calibrated) | Distance-logit (calibrated) | Verdict |
|---|---|---|---|
| primary (14 folds) | 0.618 | **0.635** | baseline still wins |
| ex_boem (11 folds) | **0.418** | 0.397 | **GBM wins** |

The refinement worked as theory predicted — the GBM jumped from 0.540 → 0.618 on
primary and now **beats the baseline on the clean, true-outcome ex-BOEM subset**
(0.418 vs 0.397, reversing the attempt-1 tie). But on the primary set the
baseline is inflated by the BOEM lease-proxy tautology (diagnosis item 2), and
0.618 < 0.635 there. **The gate requires both sets. It fails.** Moving the bar to
"ex-BOEM only" because that is the set the model wins would be exactly the
post-hoc goalpost-shift §9.8 forbids — so the honest stop stands.

What this second attempt *does* establish: the GBM has real, measurable
within-fold ranking skill on genuine outcomes — it is not noise. It simply
cannot clear a distance heuristic that is quasi-self-fulfilling on the
BOEM-dominated primary label set. That is a sharper, more useful negative result
than attempt 1, not a softer one.

## Diagnosis (why, honestly)

1. **The label geography favors the baseline.** All five regulators cover
   mature basins. Within a mature basin, drilling history is a near-optimal
   predictor and 5 km-resolution physics adds little; the model's would-be
   edge — cross-province generalization — is precisely what LOPO removes the
   crutches for, and the physics channels did not carry it.
2. **The BOEM proxy is quasi-tautological for baseline (b).** The GoM label
   derives from lease→field adjacency — a spatial-neighborhood construct — so
   distance-to-discovery on that fold (n=11,874, 69% of primary) is close to
   self-fulfilling (fold PR-AUC 0.732). This inflates the baseline on
   `primary`; but the gate also failed (tie) on the clean subset, so the
   proxy is not the whole story.
3. **Cross-fold score-scale artifact.** Pooled PR-AUC (0.540) sits below every
   per-fold GBM value (0.42–0.74) because per-fold models emit incomparable
   score scales; the single-feature logit suffers less. A per-fold-calibrated
   pooling would be a defensible metric refinement — but it was not
   pre-stated, and applying it after seeing the result would be moving the
   bar. Recorded as methodology commentary only.
4. A physics-only CNN sees strictly less information than this GBM (which had
   physics AND drilling history). A CNN pass after a GBM tie is implausible;
   spending GPU-hours to find that out would be gate-shopping.

## What §9.8 prescribes (and what ships)

> "Stop, write up the negative result honestly, ship the GBM diagnostic +
> Discovery Monitor + agents on user-supplied Pg, and say so publicly. A
> documented negative result with clean methodology is still a portfolio
> asset; a fake heatmap is a liability."

- **No prospectivity heatmap ships.** The MAP panel does not get a model
  raster; wells + context layers only.
- The /validation page renders this table — the baselines beating the model
  is the falsification gate working, displayed as a first-class feature.
- The GBM remains available as a *diagnostic* (feature importances, per-fold
  behavior), never as a probability map.
- Phase 5 agents take **user-supplied Pg** with the memo stating its origin.

## Legitimate future avenues (research, not resurrection)

Each would require re-passing this same gate, pre-stated: frontier negative
data (licensing-round relinquishments), finer-resolution geophysics, per-fold
calibrated pooling defined *before* the next run, label-noise-robust
objectives for the BOEM proxy. None are part of this phase.
