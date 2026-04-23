"""
SmartShelf — Demand Forecasting Model
======================================
XGBoost Regressor predicting daily units_sold per product-store.

Key design decisions:
  - Time-based split (70/15/15 chronological) — never random split for time series
  - TimeSeriesSplit CV for hyperparameter tuning — respects temporal ordering
  - Early stopping on validation set to prevent overfitting
  - Regularization: max_depth cap, min_child_weight, L1/L2 penalties
  - MLflow integration: logs params, metrics, feature importance, model artifact
"""

import logging
from typing import Optional

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
import subprocess

# ── Hardware Safety ────────────────────────────────────────────────────────
try:
    HAS_GPU = subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
except Exception:
    HAS_GPU = False

DEVICE_XGB = "cuda" if HAS_GPU else "cpu"
# Force low thread count on CPU to prevent laptop freezing!
N_JOBS_CV = 2 if HAS_GPU else 1  
N_JOBS_MODEL = -1 if HAS_GPU else 2  

from smartshelf.config import (
    DEMAND_FEATURES,
    DEMAND_TARGET,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MODEL_NAME_DEMAND,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# DATA SPLITTING
# ═════════════════════════════════════════════════════════════════════════════

def time_based_split(df: pd.DataFrame, date_col: str = "date",
                     train_pct: float = 0.70, val_pct: float = 0.15):
    """
    Chronological 70/15/15 split.
    Returns (train, val, test) DataFrames.
    """
    df = df.sort_values(date_col).reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_pct)
    val_end = int(n * (train_pct + val_pct))

    train = df.iloc[:train_end]
    val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:]

    logger.info(f"Split: train={len(train)}, val={len(val)}, test={len(test)}")
    return train, val, test


# ═════════════════════════════════════════════════════════════════════════════
# METRICS
# ═════════════════════════════════════════════════════════════════════════════

def compute_metrics(y_true, y_pred) -> dict:
    """Compute regression metrics for demand forecasting."""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)

    # MAPE — handle zeros
    mask = y_true != 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
    else:
        mape = 0.0

    return {"rmse": round(rmse, 4), "mae": round(mae, 4),
            "r2": round(r2, 4), "mape": round(mape, 2)}


# ═════════════════════════════════════════════════════════════════════════════
# HYPERPARAMETER SEARCH SPACE
# ═════════════════════════════════════════════════════════════════════════════

PARAM_DISTRIBUTIONS = {
    "n_estimators": [100, 200, 300, 500],
    "max_depth": [3, 4, 5, 6],               # capped to prevent overfitting
    "learning_rate": [0.01, 0.03, 0.05, 0.1],
    "min_child_weight": [3, 5, 7, 10],        # prevents overfitting on sparse groups
    "subsample": [0.7, 0.8, 0.9],             # row subsampling
    "colsample_bytree": [0.7, 0.8, 0.9],      # column subsampling
    "reg_alpha": [0, 0.01, 0.1, 1.0],         # L1 regularization
    "reg_lambda": [1.0, 2.0, 5.0, 10.0],      # L2 regularization
    "gamma": [0, 0.1, 0.3, 0.5],              # min split loss
}


# ═════════════════════════════════════════════════════════════════════════════
# TRAINING
# ═════════════════════════════════════════════════════════════════════════════

def train_demand_model(
    df: pd.DataFrame,
    tune: bool = True,
    n_iter: int = 20,
) -> tuple[xgb.XGBRegressor, dict, pd.DataFrame]:
    """
    Train the demand forecasting model.

    Args:
        df: Feature DataFrame with all DEMAND_FEATURES + DEMAND_TARGET columns.
        tune: Whether to run hyperparameter search.
        n_iter: Number of random search iterations.

    Returns:
        (trained_model, test_metrics, test_predictions_df)
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    # ── Prepare features ─────────────────────────────────────────────────
    available_features = [f for f in DEMAND_FEATURES if f in df.columns]
    missing = set(DEMAND_FEATURES) - set(available_features)
    if missing:
        logger.warning(f"Missing features (will be skipped): {missing}")

    # ── Split ────────────────────────────────────────────────────────────
    train, val, test = time_based_split(df)

    X_train = train[available_features].fillna(0)
    y_train = train[DEMAND_TARGET]
    X_val = val[available_features].fillna(0)
    y_val = val[DEMAND_TARGET]
    X_test = test[available_features].fillna(0)
    y_test = test[DEMAND_TARGET]

    with mlflow.start_run(run_name="demand_model_training") as run:
        mlflow.set_tag("model_type", "demand_forecasting")
        mlflow.set_tag("algorithm", "XGBoost")
        mlflow.log_param("n_features", len(available_features))
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("val_size", len(X_val))
        mlflow.log_param("test_size", len(X_test))
        mlflow.log_param("feature_list", str(available_features))

        if tune:
            # ── Hyperparameter tuning with TimeSeriesSplit CV ────────────
            logger.info(f"Running RandomizedSearchCV ({n_iter} iterations)...")
            cv = TimeSeriesSplit(n_splits=3)
            base_model = xgb.XGBRegressor(
                objective="reg:squarederror",
                tree_method="hist",
                device=DEVICE_XGB,
                n_jobs=N_JOBS_MODEL,
                random_state=42,
                early_stopping_rounds=20,
            )
            search = RandomizedSearchCV(
                base_model,
                param_distributions=PARAM_DISTRIBUTIONS,
                n_iter=n_iter,
                cv=cv,
                scoring="neg_root_mean_squared_error",
                n_jobs=N_JOBS_CV,
                random_state=42,
                verbose=1,
            )
            search.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            model = search.best_estimator_
            mlflow.log_params({f"best_{k}": v for k, v in search.best_params_.items()})
            logger.info(f"Best params: {search.best_params_}")
        else:
            # ── Default model with anti-overfitting settings ─────────────
            model = xgb.XGBRegressor(
                n_estimators=300,
                max_depth=5,
                learning_rate=0.05,
                min_child_weight=5,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=5.0,
                gamma=0.1,
                objective="reg:squarederror",
                tree_method="hist",
                device=DEVICE_XGB,
                n_jobs=N_JOBS_MODEL,
                early_stopping_rounds=20,
                random_state=42,
            )
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            mlflow.log_params(model.get_params())

        # ── Evaluate ─────────────────────────────────────────────────────
        train_metrics = compute_metrics(y_train, model.predict(X_train))
        val_metrics = compute_metrics(y_val, model.predict(X_val))
        test_preds = model.predict(X_test)
        test_preds = np.maximum(test_preds, 0)  # demand can't be negative
        test_metrics = compute_metrics(y_test.values, test_preds)

        # Log all metrics
        for split, metrics in [("train", train_metrics), ("val", val_metrics), ("test", test_metrics)]:
            for k, v in metrics.items():
                mlflow.log_metric(f"{split}_{k}", v)

        # ── Overfitting check ────────────────────────────────────────────
        overfit_ratio = train_metrics["rmse"] / (test_metrics["rmse"] + 1e-8)
        mlflow.log_metric("overfit_ratio", round(overfit_ratio, 4))
        if overfit_ratio < 0.5:
            logger.warning(
                f"⚠️ Possible overfitting: train RMSE ({train_metrics['rmse']}) "
                f"much lower than test RMSE ({test_metrics['rmse']})"
            )

        # ── Feature importance ───────────────────────────────────────────
        importance = pd.DataFrame({
            "feature": available_features,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)
        mlflow.log_text(importance.to_csv(index=False), "feature_importance.csv")

        # ── Log & register model ─────────────────────────────────────────
        mlflow.xgboost.log_model(
            model,
            artifact_path="demand_model",
            registered_model_name=MODEL_NAME_DEMAND,
        )

        logger.info(f"Test metrics: {test_metrics}")
        logger.info(f"Model registered as '{MODEL_NAME_DEMAND}' (run: {run.info.run_id})")

    # Build test predictions DataFrame for downstream use
    test_pred_df = test[["product_id", "store_id", "date"]].copy()
    test_pred_df["predicted_demand"] = test_preds
    test_pred_df["actual_demand"] = y_test.values

    return model, test_metrics, test_pred_df
