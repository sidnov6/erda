"""Synthetic tests for isotonic calibration (spec §9.7, §11.3).

All data here is SYNTHETIC test artifact with analytically derivable expectations —
it never enters data/. Offline, seeded, deterministic.
"""

import numpy as np
import pytest
from sklearn.isotonic import IsotonicRegression

from erda_models.calibration import apply_calibration, calibration_summary, fit_isotonic

SEED = 20260718


def _miscalibrated_dataset(n: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    """True P(y=1) = p, but the model reports raw = p**3: monotone yet badly miscalibrated."""
    rng = np.random.default_rng(SEED)
    p_true = rng.uniform(0.05, 0.95, size=n)
    labels = (rng.uniform(size=n) < p_true).astype(float)
    raw = p_true**3
    return raw, labels


class TestFitIsotonic:
    def test_returns_configured_isotonic_regression(self):
        raw, labels = _miscalibrated_dataset(200)
        model = fit_isotonic(raw, labels)
        assert isinstance(model, IsotonicRegression)
        assert model.out_of_bounds == "clip"
        assert model.y_min == 0.0
        assert model.y_max == 1.0

    def test_pava_pooling_matches_hand_computed_solution(self):
        # PAV on labels (0, 1, 0, 1) at increasing scores pools the middle
        # violator pair (1, 0) to its mean 0.5 — the textbook analytic solution.
        model = fit_isotonic([0.1, 0.2, 0.3, 0.4], [0, 1, 0, 1])
        np.testing.assert_allclose(
            apply_calibration(model, [0.1, 0.2, 0.3, 0.4]), [0.0, 0.5, 0.5, 1.0]
        )

    def test_perfectly_separated_labels_reach_zero_brier(self):
        raw = np.array([0.1, 0.2, 0.3, 0.4])
        labels = np.array([0.0, 0.0, 1.0, 1.0])
        model = fit_isotonic(raw, labels)
        summary = calibration_summary(labels, raw, apply_calibration(model, raw))
        assert summary["brier_calibrated"] == pytest.approx(0.0, abs=1e-12)

    def test_single_class_all_zeros_raises(self):
        with pytest.raises(ValueError, match="single class"):
            fit_isotonic([0.1, 0.5, 0.9], [0, 0, 0])

    def test_single_class_all_ones_raises(self):
        with pytest.raises(ValueError, match="single class"):
            fit_isotonic([0.1, 0.5, 0.9], [1, 1, 1])

    def test_non_binary_labels_raise(self):
        with pytest.raises(ValueError, match="binary"):
            fit_isotonic([0.1, 0.5, 0.9], [0.0, 0.5, 1.0])

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="mismatch"):
            fit_isotonic([0.1, 0.5], [0, 1, 1])

    def test_empty_and_nonfinite_inputs_raise(self):
        with pytest.raises(ValueError, match="empty"):
            fit_isotonic([], [])
        with pytest.raises(ValueError, match="NaN or infinite"):
            fit_isotonic([0.1, np.nan, 0.9], [0, 1, 1])


class TestApplyCalibration:
    def test_output_within_unit_interval(self):
        raw, labels = _miscalibrated_dataset()
        model = fit_isotonic(raw, labels)
        rng = np.random.default_rng(SEED + 1)
        out = apply_calibration(model, rng.uniform(-2.0, 3.0, size=500))
        assert np.all(out >= 0.0)
        assert np.all(out <= 1.0)
        assert np.all(np.isfinite(out))

    def test_out_of_range_scores_clip_to_boundary_probabilities(self):
        raw, labels = _miscalibrated_dataset(1000)
        model = fit_isotonic(raw, labels)
        lo_edge, hi_edge = apply_calibration(model, [raw.min(), raw.max()])
        below, above = apply_calibration(model, [raw.min() - 10.0, raw.max() + 10.0])
        assert below == pytest.approx(lo_edge)
        assert above == pytest.approx(hi_edge)

    def test_calibration_reduces_brier_on_miscalibrated_scores(self):
        # In-sample this is an analytic guarantee: isotonic regression is the
        # least-squares fit over monotone maps of the score, and identity is one
        # such map, so brier_calibrated <= brier_raw always. On raw = p_true**3
        # the gap is large.
        raw, labels = _miscalibrated_dataset()
        model = fit_isotonic(raw, labels)
        summary = calibration_summary(labels, raw, apply_calibration(model, raw))
        assert summary["brier_calibrated"] < summary["brier_raw"]
        assert summary["brier_calibrated"] < summary["brier_raw"] - 0.01

    def test_ranking_preserved_with_ties_allowed(self):
        from scipy.stats import spearmanr

        raw, labels = _miscalibrated_dataset()
        model = fit_isotonic(raw, labels)
        calibrated = apply_calibration(model, raw)
        summary = calibration_summary(labels, raw, calibrated)
        assert summary["monotone"] is True
        # Spearman on the calibrated vs raw ordering: isotonic only introduces
        # ties (pooled blocks), never inversions, so correlation stays ~1.
        rho = spearmanr(raw, calibrated).statistic
        assert rho > 0.99


class TestCalibrationSummary:
    def test_brier_values_match_hand_computation(self):
        y = [0.0, 1.0]
        raw = [0.2, 0.6]
        cal = [0.1, 0.9]
        summary = calibration_summary(y, raw, cal)
        # brier_raw = (0.2^2 + 0.4^2)/2 = 0.10 ; brier_calibrated = (0.1^2 + 0.1^2)/2 = 0.01
        assert summary["brier_raw"] == pytest.approx(0.10)
        assert summary["brier_calibrated"] == pytest.approx(0.01)
        assert summary["monotone"] is True

    def test_monotone_false_when_ranking_inverted(self):
        raw = [0.1, 0.2, 0.3]
        inverted = [0.9, 0.5, 0.1]
        summary = calibration_summary([0, 1, 1], raw, inverted)
        assert summary["monotone"] is False

    def test_monotone_true_with_tied_raw_scores_any_order(self):
        # Tied raw scores may map to differing calibrated values in any order;
        # only strict raw inequalities constrain the calibrated ordering.
        raw = [0.5, 0.5, 0.7]
        cal = [0.4, 0.3, 0.8]
        assert calibration_summary([0, 1, 1], raw, cal)["monotone"] is True

    def test_monotone_false_when_tie_group_straddles_higher_group(self):
        # A value in the raw=0.5 tie group exceeds a value at raw=0.7: violation.
        raw = [0.5, 0.5, 0.7]
        cal = [0.9, 0.3, 0.8]
        assert calibration_summary([0, 1, 1], raw, cal)["monotone"] is False

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="mismatch"):
            calibration_summary([0, 1], [0.1, 0.2, 0.3], [0.1, 0.2, 0.3])


class TestDeterminism:
    def test_fit_and_apply_are_deterministic(self):
        raw, labels = _miscalibrated_dataset(500)
        out_a = apply_calibration(fit_isotonic(raw, labels), raw)
        out_b = apply_calibration(fit_isotonic(raw.copy(), labels.copy()), raw.copy())
        np.testing.assert_array_equal(out_a, out_b)
