"""
SmartShelf — Drift Detection Tests
====================================
Tests for PSI calculation, KS test, and threshold logic.
"""

import numpy as np
import pytest


class TestPSI:
    """Tests for Population Stability Index."""

    def test_identical_distributions(self):
        """PSI should be ~0 for identical distributions."""
        from smartshelf.monitoring.drift_detector import compute_psi

        np.random.seed(42)
        data = np.random.normal(0, 1, 1000)
        psi = compute_psi(data, data.copy())
        assert psi < 0.01, f"PSI for identical distributions should be ~0, got {psi}"

    def test_shifted_distribution(self):
        """PSI should be high for shifted distributions."""
        from smartshelf.monitoring.drift_detector import compute_psi

        np.random.seed(42)
        expected = np.random.normal(0, 1, 1000)
        actual = np.random.normal(3, 1, 1000)  # shifted by 3σ

        psi = compute_psi(expected, actual)
        assert psi > 0.2, f"PSI for 3σ shift should be >0.2, got {psi}"

    def test_slight_shift_moderate_psi(self):
        """Small shift should give moderate PSI."""
        from smartshelf.monitoring.drift_detector import compute_psi

        np.random.seed(42)
        expected = np.random.normal(0, 1, 1000)
        actual = np.random.normal(0.5, 1, 1000)  # slight shift

        psi = compute_psi(expected, actual)
        assert 0.0 < psi < 0.5, f"PSI for slight shift should be moderate, got {psi}"

    def test_small_sample(self):
        """Should handle small samples gracefully."""
        from smartshelf.monitoring.drift_detector import compute_psi

        psi = compute_psi(np.array([1, 2, 3]), np.array([1, 2, 3]))
        assert psi == 0.0  # too few samples, returns 0

    def test_psi_non_negative(self):
        """PSI should always be ≥ 0."""
        from smartshelf.monitoring.drift_detector import compute_psi

        np.random.seed(42)
        for _ in range(10):
            expected = np.random.normal(0, 1, 100)
            actual = np.random.normal(np.random.uniform(-2, 2), 1, 100)
            psi = compute_psi(expected, actual)
            assert psi >= 0, f"PSI should be non-negative, got {psi}"


class TestPredictionDrift:
    """Tests for KS-based prediction drift."""

    def test_no_drift_same_distribution(self):
        """Same distribution should show no drift."""
        from smartshelf.monitoring.drift_detector import compute_prediction_drift

        np.random.seed(42)
        data = np.random.normal(10, 2, 500)
        result = compute_prediction_drift(data, data.copy())

        assert result["is_drifted"] == False
        assert result["p_value"] > 0.05

    def test_drift_detected_different_distribution(self):
        """Very different distributions should trigger drift."""
        from smartshelf.monitoring.drift_detector import compute_prediction_drift

        np.random.seed(42)
        training = np.random.normal(10, 2, 500)
        current = np.random.normal(30, 2, 500)  # far different

        result = compute_prediction_drift(training, current)

        assert result["is_drifted"] == True
        assert result["p_value"] < 0.05
        assert result["ks_statistic"] > 0.5

    def test_small_sample_no_crash(self):
        """Should handle tiny samples without crashing."""
        from smartshelf.monitoring.drift_detector import compute_prediction_drift

        result = compute_prediction_drift(np.array([1, 2]), np.array([1, 2]))
        assert result["is_drifted"] is False


class TestDriftReport:
    """Tests for the full drift detection pipeline."""

    def test_report_structure(self):
        """Drift report should have required keys."""
        from smartshelf.monitoring.drift_detector import run_drift_detection

        np.random.seed(42)
        training = np.random.normal(0, 1, (200, 3))
        current = np.random.normal(0, 1, (50, 3))

        import pandas as pd
        cols = ["feature_1", "feature_2", "feature_3"]
        train_df = pd.DataFrame(training, columns=cols)
        cur_df = pd.DataFrame(current, columns=cols)

        report = run_drift_detection(
            training_data=train_df,
            current_data=cur_df,
            feature_columns=cols,
        )

        assert "timestamp" in report
        assert "overall_drift" in report
        assert "drift_score" in report
        assert "feature_drift" in report
        assert "drifted_features" in report
        assert isinstance(report["overall_drift"], bool)
        assert 0 <= report["drift_score"] <= 1
