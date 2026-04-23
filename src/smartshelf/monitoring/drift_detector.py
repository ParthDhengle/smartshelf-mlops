"""
SmartShelf — Drift Detection
==============================
Monitors data and prediction drift to trigger retraining.

Implements:
  1. PSI (Population Stability Index) — detects feature distribution shifts
  2. KS Test — detects prediction distribution shifts
  3. Threshold alerts with configurable sensitivity

When drift exceeds thresholds → triggers the local Prefect training flow.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from smartshelf.config import (
    DRIFT_LOOKBACK_DAYS,
    DRIFT_REPORTS_DIR,
    KS_THRESHOLD,
    PROCESSED_DIR,
    PSI_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# PSI (POPULATION STABILITY INDEX)
# ═════════════════════════════════════════════════════════════════════════════

def compute_psi(expected: np.ndarray, actual: np.ndarray,
                n_bins: int = 10) -> float:
    """
    Compute PSI between two distributions.

    PSI < 0.1  → no significant drift
    PSI 0.1–0.2 → moderate drift (monitor)
    PSI > 0.2  → significant drift (retrain)

    Args:
        expected: reference distribution (training data)
        actual: current distribution (recent data)
        n_bins: number of bins for histogram

    Returns:
        PSI score (float ≥ 0)
    """
    # Handle edge cases
    if len(expected) < n_bins or len(actual) < n_bins:
        return 0.0

    # Create bins based on expected distribution
    breakpoints = np.percentile(expected, np.linspace(0, 100, n_bins + 1))
    breakpoints = np.unique(breakpoints)
    if len(breakpoints) < 2:
        return 0.0

    # Compute bin proportions
    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]

    # Convert to proportions with Laplace smoothing
    expected_pct = (expected_counts + 1) / (expected_counts.sum() + len(expected_counts))
    actual_pct = (actual_counts + 1) / (actual_counts.sum() + len(actual_counts))

    # PSI formula
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi)


# ═════════════════════════════════════════════════════════════════════════════
# PREDICTION DRIFT (KS TEST)
# ═════════════════════════════════════════════════════════════════════════════

def compute_prediction_drift(
    training_predictions: np.ndarray,
    current_predictions: np.ndarray,
) -> dict:
    """
    KS test on prediction distributions.
    Returns: {ks_statistic, p_value, is_drifted}
    """
    if len(training_predictions) < 10 or len(current_predictions) < 10:
        return {"ks_statistic": 0, "p_value": 1.0, "is_drifted": False}

    ks_stat, p_value = stats.ks_2samp(training_predictions, current_predictions)

    return {
        "ks_statistic": round(float(ks_stat), 4),
        "p_value": round(float(p_value), 6),
        "is_drifted": p_value < KS_THRESHOLD,
    }


# ═════════════════════════════════════════════════════════════════════════════
# FULL DRIFT CHECK
# ═════════════════════════════════════════════════════════════════════════════

def run_drift_detection(
    training_data: Optional[pd.DataFrame] = None,
    current_data: Optional[pd.DataFrame] = None,
    feature_columns: Optional[list] = None,
    prediction_col: str = "predicted_demand",
) -> dict:
    """
    Run complete drift detection suite.

    If training/current data not provided, loads from saved parquet files.

    Returns:
        {
            "timestamp": ...,
            "feature_drift": {col: {psi, is_drifted}, ...},
            "prediction_drift": {ks_statistic, p_value, is_drifted},
            "overall_drift": bool,
            "drift_score": float (0-1),
            "drifted_features": [list of drifted feature names],
        }
    """
    from smartshelf.monitoring.metrics_collector import update_drift_metrics
    
    timestamp = datetime.now().isoformat()

    # Load data if not provided
    if training_data is None:
        features_path = PROCESSED_DIR / "features.parquet"
        if not features_path.exists():
            logger.warning("No training features found for drift detection")
            return {"timestamp": timestamp, "overall_drift": False, "drift_score": 0}
        all_data = pd.read_parquet(features_path)
        # Split: training = first 70%, current = last DRIFT_LOOKBACK_DAYS
        n = len(all_data)
        training_data = all_data.iloc[:int(n * 0.7)]
        if "date" in all_data.columns:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=DRIFT_LOOKBACK_DAYS)
            current_data = all_data[all_data["date"] >= cutoff]
            if current_data.empty:
                current_data = all_data.iloc[-int(n * 0.15):]
        else:
            current_data = all_data.iloc[-int(n * 0.15):]

    # Default feature columns
    if feature_columns is None:
        numeric_cols = training_data.select_dtypes(include=[np.number]).columns.tolist()
        exclude = ["product_id", "store_id", "units_sold", prediction_col]
        feature_columns = [c for c in numeric_cols if c not in exclude]

    # ── Feature drift (PSI) ──────────────────────────────────────────────
    feature_drift = {}
    drifted_features = []

    for col in feature_columns:
        if col in training_data.columns and col in current_data.columns:
            ref = training_data[col].dropna().values
            cur = current_data[col].dropna().values
            psi = compute_psi(ref, cur)
            is_drifted = psi > PSI_THRESHOLD
            feature_drift[col] = {"psi": round(psi, 4), "is_drifted": is_drifted}
            if is_drifted:
                drifted_features.append(col)

    # ── Prediction drift (KS) ───────────────────────────────────────────
    pred_drift = {"ks_statistic": 0, "p_value": 1.0, "is_drifted": False}
    if prediction_col in training_data.columns and prediction_col in current_data.columns:
        pred_drift = compute_prediction_drift(
            training_data[prediction_col].dropna().values,
            current_data[prediction_col].dropna().values,
        )

    # ── Overall drift score ──────────────────────────────────────────────
    # Weighted: 60% feature drift + 40% prediction drift
    n_features = len(feature_columns)
    n_drifted = len(drifted_features)
    feature_drift_ratio = n_drifted / max(n_features, 1)
    pred_drift_flag = 1.0 if pred_drift["is_drifted"] else 0.0

    drift_score = 0.6 * feature_drift_ratio + 0.4 * pred_drift_flag
    overall_drift = drift_score > 0.3  # >30% of features drifted OR prediction drift

    report = {
        "timestamp": timestamp,
        "feature_drift": feature_drift,
        "prediction_drift": pred_drift,
        "overall_drift": overall_drift,
        "drift_score": round(drift_score, 4),
        "drifted_features": drifted_features,
        "n_features_checked": n_features,
        "n_features_drifted": n_drifted,
        "psi_threshold": PSI_THRESHOLD,
        "ks_threshold": KS_THRESHOLD,
    }

    # Save report
    report_path = DRIFT_REPORTS_DIR / f"drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Drift report saved → {report_path}")

    # Update Prometheus metrics
    update_drift_metrics(report)

    if overall_drift:
        logger.warning(
            f"⚠️ DRIFT DETECTED: score={drift_score:.2f}, "
            f"drifted features: {drifted_features}"
        )
    else:
        logger.info(f"✅ No significant drift (score={drift_score:.2f})")

    return report


# ═════════════════════════════════════════════════════════════════════════════
# RETRAIN TRIGGER
# ═════════════════════════════════════════════════════════════════════════════

def trigger_retraining() -> bool:
    """
    Trigger the training flow using Prefect.

    Returns True if the flow starts successfully.
    """
    try:
        from smartshelf.flows.training_flow import weekly_training_flow

        logger.info("Starting Prefect training flow after drift detection")
        weekly_training_flow()
        logger.info("✅ Retraining flow completed via Prefect")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger retraining: {e}")
        return False


def check_and_trigger() -> dict:
    """
    Run drift detection and trigger retraining if needed.
    Returns the drift report with trigger status.
    """
    report = run_drift_detection()

    if report.get("overall_drift", False):
        triggered = trigger_retraining()
        report["retrain_triggered"] = triggered
    else:
        report["retrain_triggered"] = False

    return report


if __name__ == "__main__":
    check_and_trigger()
