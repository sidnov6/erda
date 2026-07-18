"""Synthetic tests for the §9.6 baselines (spec §11.3: analytically derivable, offline).

All data here is SYNTHETIC test-fixture data (CLAUDE.md rule 4) with expectations
that follow analytically from the constructions — no real wells, no I/O, no network.
"""

import numpy as np
import pytest

from erda_models.baselines import (
    DistanceLogitBaseline,
    random_baseline,
    sediment_threshold_baseline,
)

# ---------------------------------------------------------------------------
# (a) random_baseline
# ---------------------------------------------------------------------------


class TestRandomBaseline:
    def test_seeded_reproducibility(self) -> None:
        a = random_baseline(1000, seed=42)
        b = random_baseline(1000, seed=42)
        np.testing.assert_array_equal(a, b)

    def test_different_seeds_differ(self) -> None:
        a = random_baseline(1000, seed=1)
        b = random_baseline(1000, seed=2)
        assert not np.array_equal(a, b)

    def test_matches_default_rng_analytically(self) -> None:
        # The contract is exactly "uniform [0,1) from np.random.default_rng(seed)".
        expected = np.random.default_rng(7).uniform(0.0, 1.0, size=50)
        np.testing.assert_array_equal(random_baseline(50, seed=7), expected)

    def test_shape_and_range(self) -> None:
        scores = random_baseline(500, seed=0)
        assert scores.shape == (500,)
        assert scores.dtype == np.float64
        assert np.all(scores >= 0.0)
        assert np.all(scores < 1.0)

    def test_n_zero_gives_empty(self) -> None:
        assert random_baseline(0, seed=0).shape == (0,)

    def test_negative_n_raises(self) -> None:
        with pytest.raises(ValueError, match="n must be >= 0"):
            random_baseline(-1, seed=0)


# ---------------------------------------------------------------------------
# (b) DistanceLogitBaseline — the falsification-gate opponent
# ---------------------------------------------------------------------------


def _synthetic_separable_fold(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Discoveries cluster near old discoveries; dry holes are far away.

    Positives at 0–20 km, negatives at 200–400 km: cleanly separable, so the
    single-feature logit MUST learn near -> high p(discovery) (negative slope).
    """
    rng = np.random.default_rng(seed)
    near = rng.uniform(0.0, 20.0, size=60)  # label 1: drilled next to old wells, hit
    far = rng.uniform(200.0, 400.0, size=60)  # label 0: wildcats in the void, dry
    dist = np.concatenate([near, far])
    labels = np.concatenate([np.ones(60, dtype=int), np.zeros(60, dtype=int)])
    return dist, labels


class TestDistanceLogitBaseline:
    def test_learns_near_means_discovery(self) -> None:
        dist, labels = _synthetic_separable_fold()
        model = DistanceLogitBaseline().fit(dist, labels)
        p = model.predict_proba(np.array([1.0, 300.0]))
        assert p[0] > 0.9, f"near well should score high, got {p[0]}"
        assert p[1] < 0.1, f"far well should score low, got {p[1]}"

    def test_monotonically_decreasing_in_distance(self) -> None:
        dist, labels = _synthetic_separable_fold()
        model = DistanceLogitBaseline().fit(dist, labels)
        # Single-feature logit with negative slope is monotone decreasing everywhere.
        assert model.coef_km < 0.0
        grid = np.linspace(0.0, 500.0, 201)
        p = model.predict_proba(grid)
        assert np.all(np.diff(p) <= 0.0)
        assert p[0] > p[-1]  # strictly decreasing end to end, not flat

    def test_probabilities_are_valid(self) -> None:
        dist, labels = _synthetic_separable_fold()
        p = DistanceLogitBaseline().fit(dist, labels).predict_proba(np.linspace(0, 500, 50))
        assert p.shape == (50,)
        assert np.all((p >= 0.0) & (p <= 1.0))

    def test_deterministic_across_refits(self) -> None:
        dist, labels = _synthetic_separable_fold()
        grid = np.linspace(0.0, 500.0, 101)
        p1 = DistanceLogitBaseline().fit(dist, labels).predict_proba(grid)
        p2 = DistanceLogitBaseline().fit(dist, labels).predict_proba(grid)
        np.testing.assert_array_equal(p1, p2)

    def test_fit_returns_self(self) -> None:
        dist, labels = _synthetic_separable_fold()
        model = DistanceLogitBaseline()
        assert model.fit(dist, labels) is model

    @pytest.mark.parametrize("label_value", [0, 1])
    def test_degenerate_single_class_fold_raises(self, label_value: int) -> None:
        dist = np.array([10.0, 50.0, 100.0, 250.0])
        labels = np.full(4, label_value)
        with pytest.raises(ValueError, match="degenerate single-class"):
            DistanceLogitBaseline().fit(dist, labels)

    def test_non_binary_labels_raise(self) -> None:
        with pytest.raises(ValueError, match="binary"):
            DistanceLogitBaseline().fit(np.array([1.0, 2.0, 3.0]), np.array([0, 1, 2]))

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="length mismatch"):
            DistanceLogitBaseline().fit(np.array([1.0, 2.0, 3.0]), np.array([0, 1]))

    def test_nan_distances_raise(self) -> None:
        with pytest.raises(ValueError, match="train_dist_km contains NaN"):
            DistanceLogitBaseline().fit(np.array([1.0, np.nan]), np.array([1, 0]))

    def test_nan_test_distances_raise(self) -> None:
        dist, labels = _synthetic_separable_fold()
        model = DistanceLogitBaseline().fit(dist, labels)
        with pytest.raises(ValueError, match="test_dist_km contains NaN"):
            model.predict_proba(np.array([10.0, np.inf]))

    def test_empty_distances_raise(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            DistanceLogitBaseline().fit(np.array([]), np.array([]))

    def test_predict_before_fit_raises(self) -> None:
        with pytest.raises(RuntimeError, match="before fit"):
            DistanceLogitBaseline().predict_proba(np.array([10.0]))


# ---------------------------------------------------------------------------
# (c) sediment_threshold_baseline
# ---------------------------------------------------------------------------


class TestSedimentThresholdBaseline:
    def test_exact_rule_default_threshold(self) -> None:
        sed = np.array([0.0, 499.9, 500.0, 500.1, 8000.0, np.nan])
        expected = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 0.0])  # strictly > 500; NaN -> 0
        np.testing.assert_array_equal(sediment_threshold_baseline(sed), expected)

    def test_threshold_is_strict(self) -> None:
        # Exactly at the threshold is NOT a claim.
        assert sediment_threshold_baseline(np.array([500.0]))[0] == 0.0

    def test_nan_means_no_oil_claim(self) -> None:
        # No sediment data = no oil claim (never imputed as prospective).
        np.testing.assert_array_equal(
            sediment_threshold_baseline(np.array([np.nan, np.nan])), np.array([0.0, 0.0])
        )

    def test_custom_threshold(self) -> None:
        sed = np.array([100.0, 1000.0, 2000.0])
        np.testing.assert_array_equal(
            sediment_threshold_baseline(sed, threshold_m=1000.0), np.array([0.0, 0.0, 1.0])
        )

    def test_output_is_binary_float(self) -> None:
        rng = np.random.default_rng(3)
        sed = rng.uniform(0.0, 2000.0, size=100)
        scores = sediment_threshold_baseline(sed)
        assert scores.dtype == np.float64
        assert set(np.unique(scores)) <= {0.0, 1.0}
        # Analytic cross-check against the rule applied elementwise.
        np.testing.assert_array_equal(scores, (sed > 500.0).astype(np.float64))

    def test_preserves_shape(self) -> None:
        sed = np.array([[100.0, 600.0], [np.nan, 501.0]])
        np.testing.assert_array_equal(
            sediment_threshold_baseline(sed), np.array([[0.0, 1.0], [0.0, 1.0]])
        )
