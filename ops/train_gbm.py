"""GBM spatial cross-validation vs the §9.6 baselines — the §9.8 gate runner.

Gate definition (stated before running, so the bar cannot move afterwards):
pooled out-of-fold PR-AUC of the GBM must exceed pooled PR-AUC of baseline (b)
(logit on distance-to-nearest-discovery) on BOTH label sets — primary AND
primary_ex_boem (the true-outcome subset). The BOEM proxy could gift a win on
primary alone; passing on the honest subset too is the credible claim.

Outputs: data/parquet/model_eval_gbm.json · gbm_oof.parquet · gbm feature
importances. Honest failure = print the gate verdict and exit 2.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PARQUET = REPO / "data" / "parquet"
STORE = REPO / "data" / "zarr" / "stack.zarr"
SEED = 7

LGBM_PARAMS = dict(
    objective="binary",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=63,
    min_child_samples=20,
    subsample=0.9,
    subsample_freq=1,
    colsample_bytree=0.9,
    deterministic=True,
    force_row_wise=True,
    random_state=SEED,
    verbose=-1,
)


def run_cv(wells: pd.DataFrame, ds, static: pd.DataFrame, tag: str) -> dict:
    import lightgbm as lgb

    from erda_models import baselines, evaluation, features, splits

    wells = wells.reset_index(drop=True)
    static = static.reset_index(drop=True)
    folds = splits.lopo_folds(wells)
    print(f"[{tag}] {len(folds)} folds over {len(wells)} wells")

    oof = pd.DataFrame(
        {
            "well_id": wells["well_id"],
            "label": wells["label"],
            "province_name": wells["province_name"],
            "source_id": wells["source_id"],
            "gbm": np.nan,
            "baseline_distance": np.nan,
            "baseline_random": np.nan,
            "baseline_sediment": np.nan,
        }
    )
    fold_rows = []
    for i, fold in enumerate(folds):
        train = wells.iloc[fold.train_idx]
        test = wells.iloc[fold.test_idx]
        Xtr = features.build_features(
            train, train, ds, static=static.iloc[fold.train_idx], exclude_self=True
        )
        Xte = features.build_features(test, train, ds, static=static.iloc[fold.test_idx])

        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(Xtr, train["label"])
        gbm_scores = model.predict_proba(Xte)[:, 1]

        logit = baselines.DistanceLogitBaseline()
        logit.fit(Xtr["dist_discovery_km"].values, train["label"].values)
        dist_scores = logit.predict_proba(Xte["dist_discovery_km"].values)
        rand_scores = baselines.random_baseline(len(test), seed=SEED + i)
        sed_scores = baselines.sediment_threshold_baseline(Xte["sed_thickness_m"].values)

        oof.loc[fold.test_idx, "gbm"] = gbm_scores
        oof.loc[fold.test_idx, "baseline_distance"] = dist_scores
        oof.loc[fold.test_idx, "baseline_random"] = rand_scores
        oof.loc[fold.test_idx, "baseline_sediment"] = sed_scores

        row: dict = {"fold": fold.name, **fold.meta, "n_buffer_dropped": fold.n_buffer_dropped}
        for name, scores in [
            ("gbm", gbm_scores),
            ("baseline_distance", dist_scores),
            ("baseline_random", rand_scores),
            ("baseline_sediment", sed_scores),
        ]:
            try:
                row[name] = evaluation.metric_suite(test["label"].values, scores)
            except ValueError as exc:
                row[name] = {"skipped": str(exc)}
        fold_rows.append(row)
        gbm_pr = row["gbm"].get("pr_auc")
        dist_pr = row["baseline_distance"].get("pr_auc")
        print(f"  [{fold.name[:34]:34s}] n={len(test):5d} base={fold.meta['test_base_rate']:.2f} "
              f"gbm={gbm_pr if gbm_pr is None else round(gbm_pr, 3)} "
              f"dist={dist_pr if dist_pr is None else round(dist_pr, 3)} "
              f"(buffer dropped {fold.n_buffer_dropped})")

    scored = oof.dropna(subset=["gbm"])
    pooled = {
        name: evaluation.metric_suite(scored["label"].values, scored[name].values)
        for name in ["gbm", "baseline_distance", "baseline_random", "baseline_sediment"]
    }
    return {"folds": fold_rows, "pooled": pooled, "n_scored": int(len(scored)), "oof": oof}


def main() -> int:
    import lightgbm as lgb

    from erda_geo.stack import open_stack
    from erda_models import features

    wells = pd.read_parquet(PARQUET / "wells_primary.parquet")
    ds = open_stack(STORE)
    print(f"static features for {len(wells)} wells…")
    static = features.build_static_features(wells, ds)

    primary_res = run_cv(wells, ds, static, "primary")

    ex_mask = (wells["source_id"] != "boem_bsee").values
    ex_res = run_cv(wells[ex_mask], ds, static[ex_mask], "ex_boem")

    gate = {
        "definition": "pooled OOF PR-AUC(GBM) > PR-AUC(distance logit) on primary AND ex_boem",
        "primary_gbm": primary_res["pooled"]["gbm"]["pr_auc"],
        "primary_baseline_b": primary_res["pooled"]["baseline_distance"]["pr_auc"],
        "ex_boem_gbm": ex_res["pooled"]["gbm"]["pr_auc"],
        "ex_boem_baseline_b": ex_res["pooled"]["baseline_distance"]["pr_auc"],
    }
    gate["passed"] = bool(
        gate["primary_gbm"] > gate["primary_baseline_b"]
        and gate["ex_boem_gbm"] > gate["ex_boem_baseline_b"]
    )

    # final all-data model for downstream scoring + SHAP-style importances
    X_full = features.build_features(wells, wells, ds, static=static, exclude_self=True)
    final = lgb.LGBMClassifier(**LGBM_PARAMS)
    final.fit(X_full, wells["label"])
    contrib = final.predict_proba(X_full, pred_contrib=True)
    mean_abs_contrib = np.abs(contrib[:, :-1]).mean(axis=0)
    importances = sorted(
        zip(features.FEATURE_NAMES, mean_abs_contrib.tolist(), strict=True),
        key=lambda kv: -kv[1],
    )
    (REPO / "data" / "models").mkdir(exist_ok=True)
    final.booster_.save_model(str(REPO / "data" / "models" / "gbm_full.txt"))

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "transform_version": "gbm_cv:1.0.0",
        "lgbm_params": {k: v for k, v in LGBM_PARAMS.items()},
        "gate": gate,
        "primary": {k: v for k, v in primary_res.items() if k != "oof"},
        "ex_boem": {k: v for k, v in ex_res.items() if k != "oof"},
        "feature_importance_mean_abs_contrib": importances[:20],
    }
    (PARQUET / "model_eval_gbm.json").write_text(json.dumps(report, indent=2))
    primary_res["oof"].to_parquet(PARQUET / "gbm_oof.parquet", index=False)

    print("\n================ FALSIFICATION GATE (§9.8) ================")
    print(f"primary : GBM {gate['primary_gbm']:.4f} vs distance-logit "
          f"{gate['primary_baseline_b']:.4f}")
    print(f"ex_boem : GBM {gate['ex_boem_gbm']:.4f} vs distance-logit "
          f"{gate['ex_boem_baseline_b']:.4f}")
    print(f"GATE: {'PASSED' if gate['passed'] else 'FAILED — honest stop (§9.8)'}")
    return 0 if gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
