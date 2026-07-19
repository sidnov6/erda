"""Synthetic, hand-computable tests for erda_models.evaluation (spec §11.3).

Every expected value below is derived analytically in comments — no fixtures,
no I/O, no randomness. Clearly labelled synthetic test data.
"""

import math

import numpy as np
import pandas as pd
import pytest

from erda_models.evaluation import (
    FOLD_TABLE_COLUMNS,
    POOLED_LABEL,
    fold_table,
    metric_suite,
    pooled_metrics,
    rank_calibrate_within_fold,
    reliability_bins,
)

# ---------------------------------------------------------------- metric_suite


def test_perfect_ranking_auc_metrics() -> None:
    # 2 positives ranked strictly above 8 negatives -> PR-AUC = ROC-AUC = 1.
    y_true = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    y_score = [0.95, 0.90, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]
    m = metric_suite(y_true, y_score)
    assert m["pr_auc"] == pytest.approx(1.0)
    assert m["roc_auc"] == pytest.approx(1.0)
    assert m["n"] == 10
    assert m["base_rate"] == pytest.approx(0.2)


def test_perfect_ranking_lift_is_inverse_base_rate() -> None:
    # n=10 -> top decile is ceil(10/10)=1 row; top row is positive ->
    # precision@top = 1 -> lift = 1 / base_rate = 1 / 0.2 = 5.
    y_true = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    y_score = [0.95, 0.90, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05]
    m = metric_suite(y_true, y_score)
    assert m["lift_top_decile"] == pytest.approx(5.0)


def test_hand_computed_pr_and_roc_auc() -> None:
    # Ranking by score desc: [1, 0, 1, 0].
    # Average precision = mean of precision at each positive:
    #   rank 1 -> 1/1, rank 3 -> 2/3  ->  AP = (1 + 2/3)/2 = 5/6.
    # ROC-AUC = correctly ordered (pos, neg) pairs / 4 = 3/4.
    y_true = [1, 0, 1, 0]
    y_score = [0.9, 0.8, 0.7, 0.1]
    m = metric_suite(y_true, y_score)
    assert m["pr_auc"] == pytest.approx(5.0 / 6.0)
    assert m["roc_auc"] == pytest.approx(0.75)


def test_brier_four_point_hand_computed() -> None:
    # ((1-0.9)^2 + (0-0.1)^2 + (1-0.6)^2 + (0-0.4)^2) / 4
    #   = (0.01 + 0.01 + 0.16 + 0.16) / 4 = 0.085
    m = metric_suite([1, 0, 1, 0], [0.9, 0.1, 0.6, 0.4])
    assert m["brier"] == pytest.approx(0.085)


def test_brier_zero_when_scores_equal_labels() -> None:
    m = metric_suite([1, 0, 1, 0], [1.0, 0.0, 1.0, 0.0])
    assert m["brier"] == pytest.approx(0.0)


def test_lift_tie_handling_stable_sort_positives_first() -> None:
    # All scores tied: stable sort keeps original order, so the top
    # ceil(20/10)=2 rows are indices 0 and 1 (both positive).
    # precision@top = 1, base_rate = 4/20 = 0.2 -> lift = 5.
    y_true = [1, 1, 1, 1] + [0] * 16
    y_score = [0.5] * 20
    m = metric_suite(y_true, y_score)
    assert m["lift_top_decile"] == pytest.approx(5.0)
    assert m["roc_auc"] == pytest.approx(0.5)  # constant scores rank nothing


def test_lift_tie_handling_stable_sort_positives_last() -> None:
    # Same tie but positives at the end: top-2 rows are negatives -> lift 0.
    y_true = [0] * 16 + [1, 1, 1, 1]
    y_score = [0.5] * 20
    assert metric_suite(y_true, y_score)["lift_top_decile"] == pytest.approx(0.0)


def test_lift_top_k_is_ceil_of_n_over_10() -> None:
    # n=5 -> k=ceil(0.5)=1; top row positive -> lift = 1 / (1/5) = 5.
    m5 = metric_suite([1, 0, 0, 0, 0], [0.9, 0.8, 0.7, 0.6, 0.5])
    assert m5["lift_top_decile"] == pytest.approx(5.0)
    # n=11 -> k=ceil(1.1)=2; top-2 = [1, 0] -> precision 1/2,
    # base_rate 2/11 -> lift = (1/2)/(2/11) = 11/4 = 2.75.
    y_true = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
    y_score = [0.95 - 0.05 * i for i in range(11)]  # strictly decreasing
    assert metric_suite(y_true, y_score)["lift_top_decile"] == pytest.approx(2.75)


def test_single_class_raises_value_error() -> None:
    with pytest.raises(ValueError, match="single class"):
        metric_suite([0, 0, 0], [0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="single class"):
        metric_suite([1, 1], [0.6, 0.7])


def test_malformed_inputs_raise_value_error() -> None:
    with pytest.raises(ValueError, match="mismatch"):
        metric_suite([1, 0], [0.5])
    with pytest.raises(ValueError, match="empty"):
        metric_suite([], [])
    with pytest.raises(ValueError, match="only 0 and 1"):
        metric_suite([1, 2], [0.5, 0.5])
    with pytest.raises(ValueError, match="finite"):
        metric_suite([1, 0], [0.5, float("nan")])


def test_metric_suite_is_deterministic_and_pure() -> None:
    y_true = np.array([1, 0, 1, 0])
    y_score = np.array([0.9, 0.8, 0.7, 0.1])
    before = (y_true.copy(), y_score.copy())
    assert metric_suite(y_true, y_score) == metric_suite(y_true, y_score)
    np.testing.assert_array_equal(y_true, before[0])  # inputs untouched
    np.testing.assert_array_equal(y_score, before[1])


# ------------------------------------------------------------ reliability_bins


def test_rank_calibrate_within_fold_hand_computed() -> None:
    # Two folds. Fold "A": scores [0.1, 0.9, 0.5] → avg-ranks [1,3,2] / 3 =
    # [1/3, 1, 2/3]. Fold "B": scores [100, 200] (a different, larger SCALE) →
    # ranks [1,2] / 2 = [0.5, 1.0]. The calibration erases B's inflated scale.
    folds = np.array(["A", "A", "A", "B", "B"])
    scores = np.array([0.1, 0.9, 0.5, 100.0, 200.0])
    out = rank_calibrate_within_fold(folds, scores)
    assert np.allclose(out, [1 / 3, 1.0, 2 / 3, 0.5, 1.0])
    assert out.min() > 0.0 and out.max() <= 1.0


def test_rank_calibrate_ties_take_average_rank() -> None:
    # A three-way tie in one fold → all get the mean rank (1+2+3)/3 / 3 = 2/3.
    folds = np.array(["A", "A", "A"])
    out = rank_calibrate_within_fold(folds, np.array([0.4, 0.4, 0.4]))
    assert np.allclose(out, [2 / 3, 2 / 3, 2 / 3])


def test_rank_calibrate_is_pure_and_validates() -> None:
    folds = np.array(["A", "A", "B"])
    scores = np.array([0.2, 0.8, 0.5])
    first = rank_calibrate_within_fold(folds, scores)
    second = rank_calibrate_within_fold(folds, scores)
    assert np.array_equal(first, second)  # deterministic
    assert np.array_equal(scores, [0.2, 0.8, 0.5])  # no mutation
    with pytest.raises(ValueError):
        rank_calibrate_within_fold(np.array(["A", "B"]), np.array([1.0]))


def test_reliability_bins_exact_four_points() -> None:
    # One point per occupied decile bin; six deciles are empty.
    y_true = [0, 1, 1, 1]
    y_score = [0.05, 0.15, 0.95, 0.85]
    df = reliability_bins(y_true, y_score, n_bins=10)
    assert list(df.columns) == ["bin_lo", "bin_hi", "mean_score", "frac_positive", "n"]
    assert len(df) == 4  # empty bins are absent, never interpolated
    assert df["bin_lo"].tolist() == pytest.approx([0.0, 0.1, 0.8, 0.9])
    assert df["bin_hi"].tolist() == pytest.approx([0.1, 0.2, 0.9, 1.0])
    assert df["mean_score"].tolist() == pytest.approx([0.05, 0.15, 0.85, 0.95])
    assert df["frac_positive"].tolist() == pytest.approx([0.0, 1.0, 1.0, 1.0])
    assert df["n"].tolist() == [1, 1, 1, 1]


def test_reliability_bins_groups_scores_in_same_bin() -> None:
    # Both scores fall in [0.6, 0.7): mean_score = 0.65, frac_positive = 1/2.
    df = reliability_bins([1, 0], [0.62, 0.68], n_bins=10)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["bin_lo"] == pytest.approx(0.6)
    assert row["bin_hi"] == pytest.approx(0.7)
    assert row["mean_score"] == pytest.approx(0.65)
    assert row["frac_positive"] == pytest.approx(0.5)
    assert row["n"] == 2


def test_reliability_bins_edge_scores() -> None:
    # 0.0 -> first bin; 1.0 -> last (closed) bin; an edge value like 0.3
    # lands in the bin whose lower edge it equals.
    df = reliability_bins([0, 1, 0], [0.0, 1.0, 0.3], n_bins=10)
    assert df["bin_lo"].tolist() == pytest.approx([0.0, 0.3, 0.9])
    assert df["n"].tolist() == [1, 1, 1]


def test_reliability_bins_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        reliability_bins([1, 0], [0.5, 1.2])
    with pytest.raises(ValueError, match="n_bins"):
        reliability_bins([1, 0], [0.5, 0.6], n_bins=0)


# ------------------------------------------------------ fold_table and pooling


def _two_fold_case() -> list[dict]:
    # Fold A perfectly ranked; fold B perfectly inverted.
    return [
        {"fold": "province_a", "y_true": [1, 0], "y_score": [0.9, 0.1]},
        {"fold": "province_b", "y_true": [1, 0], "y_score": [0.2, 0.8]},
    ]


def test_fold_table_per_fold_rows_hand_computed() -> None:
    df = fold_table(_two_fold_case())
    assert list(df.columns) == list(FOLD_TABLE_COLUMNS)
    assert df["fold"].tolist() == ["province_a", "province_b", POOLED_LABEL]
    a, b = df.iloc[0], df.iloc[1]
    assert a["pr_auc"] == pytest.approx(1.0)  # perfect ranking
    assert a["roc_auc"] == pytest.approx(1.0)
    # Fold B ranking desc: [0, 1] -> AP = precision at the one positive
    # (rank 2) = 1/2; ROC-AUC = 0 ordered pairs.
    assert b["pr_auc"] == pytest.approx(0.5)
    assert b["roc_auc"] == pytest.approx(0.0)
    assert not a["skipped"] and not b["skipped"]


def test_pooled_row_is_concatenated_oof_not_mean_of_folds() -> None:
    # Pooled arrays: y=[1,0,1,0], s=[0.9,0.1,0.2,0.8]; ranking desc:
    # [1(0.9), 0(0.8), 1(0.2), 0(0.1)] -> AP = (1/1 + 2/3)/2 = 5/6.
    # Mean of fold PR-AUCs = (1.0 + 0.5)/2 = 0.75 != 5/6: pooled != mean.
    df = fold_table(_two_fold_case())
    pooled = df.iloc[-1]
    assert pooled["fold"] == POOLED_LABEL
    assert pooled["pr_auc"] == pytest.approx(5.0 / 6.0)
    assert pooled["n"] == 4
    mean_of_folds = df.iloc[:-1]["pr_auc"].mean()
    assert not math.isclose(pooled["pr_auc"], mean_of_folds)
    # Pooled lift: k=ceil(4/10)=1, top row 0.9 is positive -> 1/0.5 = 2.
    assert pooled["lift_top_decile"] == pytest.approx(2.0)


def test_pooled_metrics_helper_matches_concatenation() -> None:
    per_fold = _two_fold_case()
    pooled = pooled_metrics(per_fold)
    direct = metric_suite([1, 0, 1, 0], [0.9, 0.1, 0.2, 0.8])
    assert pooled == direct


def test_single_class_fold_marked_skipped_but_pooled_includes_it() -> None:
    per_fold = [
        {"fold": "mixed", "y_true": [1, 0], "y_score": [0.9, 0.1]},
        {"fold": "all_negative", "y_true": [0, 0, 0], "y_score": [0.3, 0.2, 0.1]},
    ]
    df = fold_table(per_fold)
    skipped = df[df["fold"] == "all_negative"].iloc[0]
    assert bool(skipped["skipped"]) is True
    assert pd.isna(skipped["pr_auc"]) and pd.isna(skipped["roc_auc"])
    assert skipped["n"] == 3 and skipped["base_rate"] == pytest.approx(0.0)
    pooled = df.iloc[-1]
    assert pooled["n"] == 5  # skipped fold's samples still pooled
    assert pooled["base_rate"] == pytest.approx(1.0 / 5.0)
    assert not pooled["skipped"]


def test_fold_table_malformed_input_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        fold_table([])
    with pytest.raises(ValueError, match="missing required key"):
        fold_table([{"y_true": [1, 0], "y_score": [0.9, 0.1]}])
    with pytest.raises(ValueError, match="missing required key"):
        fold_table([{"fold": "a", "y_true": [1, 0]}])
