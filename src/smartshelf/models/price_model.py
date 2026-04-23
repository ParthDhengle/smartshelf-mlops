"""
SmartShelf — Price Optimization Model
======================================
Predicts the optimal selling price that maximizes profit for each product-store.

Approach:
  1. Uses demand predictions as a key input feature (model dependency)
  2. Learns the price–demand relationship from historical data
  3. Computes price elasticity from the demand curve
  4. Searches for the price point that maximizes:
       profit = (price - cost) × predicted_demand_at_price

The model predicts expected demand at various price points, then an
optimization step selects the profit-maximizing price.

Architecture: LightGBM (better for this task due to faster training on
the price-sweep inference step).
"""

import logging

import lightgbm as lgb
import mlflow
import mlflow.lightgbm
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit

from smartshelf.config import (
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MODEL_NAME_PRICE,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# PRICE MODEL FEATURES
# ═════════════════════════════════════════════════════════════════════════════

# The price model predicts demand_at_price. We then sweep prices to find optimum.
PRICE_MODEL_FEATURES = [
    "selling_price",          # the price we're evaluating
    "competitor_price",
    "discount_pct",
    "cost_price",
    "base_sell_price",
    "gross_margin",
    "predicted_demand",       # from demand model (dependency)
    "units_sold_roll_mean_7",
    "units_sold_roll_mean_14",
    "units_sold_roll_mean_28",
    "day_of_week", "month", "quarter", "is_weekend", "is_holiday",
    "temperature_c", "rainfall_mm", "humidity_pct",
    "inflation_rate", "cpi",
    "store_size_sqft",
    "perishable", "shelf_life_days",
    "store_type_encoded", "category_encoded", "season_encoded",
]

# Target: units_sold (we model demand as f(price, context) then optimize)
PRICE_MODEL_TARGET = "units_sold"


# ═════════════════════════════════════════════════════════════════════════════
# HYPERPARAMETER SEARCH
# ═════════════════════════════════════════════════════════════════════════════

PARAM_DISTRIBUTIONS = {
    "n_estimators": [100, 200, 300, 500],
    "max_depth": [3, 4, 5, 6],
    "learning_rate": [0.01, 0.03, 0.05, 0.1],
    "num_leaves": [15, 31, 63],
    "min_child_samples": [10, 20, 30, 50],
    "subsample": [0.7, 0.8, 0.9],
    "colsample_bytree": [0.7, 0.8, 0.9],
    "reg_alpha": [0, 0.01, 0.1, 1.0],
    "reg_lambda": [1.0, 2.0, 5.0],
}


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: COMPUTE METRICS
# ═════════════════════════════════════════════════════════════════════════════

def compute_metrics(y_true, y_pred) -> dict:
    """Regression metrics for demand-at-price model."""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4)}


# ═════════════════════════════════════════════════════════════════════════════
# PRICE ELASTICITY
# ═════════════════════════════════════════════════════════════════════════════

def compute_price_elasticity(model, X_base: pd.DataFrame,
                              price_col: str = "selling_price",
                              delta_pct: float = 0.01) -> np.ndarray:
    """
    Estimate price elasticity of demand at each data point.
    E = (ΔQ/Q) / (ΔP/P)
    Uses model predictions at price and price+δ.
    """
    X_high = X_base.copy()
    X_high[price_col] = X_high[price_col] * (1 + delta_pct)

    q_base = model.predict(X_base)
    q_high = model.predict(X_high)

    dq = q_high - q_base
    dp = delta_pct  # proportional change

    elasticity = (dq / (q_base + 1e-8)) / dp
    return elasticity


# ═════════════════════════════════════════════════════════════════════════════
# OPTIMAL PRICE SEARCH
# ═════════════════════════════════════════════════════════════════════════════

def find_optimal_prices(model, X: pd.DataFrame,
                         cost_prices: np.ndarray,
                         price_col: str = "selling_price",
                         n_steps: int = 20) -> pd.DataFrame:
    """
    Grid search over price range [0.8× cost, 2.5× base_price] for each row.
    Returns DataFrame with optimal_price, expected_demand, expected_profit.
    """
    base_prices = X[price_col].values
    results = []

    for i in range(len(X)):
        row = X.iloc[[i]]
        cost = cost_prices[i]
        base_p = base_prices[i]

        # Search between 80% of cost and 250% of base price
        price_range = np.linspace(max(cost * 0.8, 1.0), base_p * 2.5, n_steps)
        best_profit = -np.inf
        best_price = base_p
        best_demand = 0

        for p in price_range:
            row_copy = row.copy()
            row_copy[price_col] = p
            demand = max(model.predict(row_copy)[0], 0)
            profit = (p - cost) * demand
            if profit > best_profit:
                best_profit = profit
                best_price = p
                best_demand = demand

        results.append({
            "optimal_price": round(best_price, 2),
            "expected_demand": round(best_demand, 2),
            "expected_profit": round(best_profit, 2),
        })

    return pd.DataFrame(results)


# ═════════════════════════════════════════════════════════════════════════════
# TRAINING
# ═════════════════════════════════════════════════════════════════════════════

def train_price_model(
    df: pd.DataFrame,
    tune: bool = True,
    n_iter: int = 15,
) -> tuple[lgb.LGBMRegressor, dict, pd.DataFrame]:
    """
    Train the price optimization model.

    Args:
        df: Feature DataFrame. Must include 'predicted_demand' column
            (output of the demand model).
        tune: Whether to run hyperparameter tuning.
        n_iter: RandomizedSearchCV iterations.

    Returns:
        (trained_model, test_metrics, optimization_results_df)
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    # ── Prepare features ─────────────────────────────────────────────────
    available = [f for f in PRICE_MODEL_FEATURES if f in df.columns]
    missing = set(PRICE_MODEL_FEATURES) - set(available)
    if missing:
        logger.warning(f"Missing features: {missing}")

    if "cost_price" not in df.columns and "base_cost_price" in df.columns:
        df["cost_price"] = df["base_cost_price"]

    # ── Time-based split ─────────────────────────────────────────────────
    df_sorted = df.sort_values("date").reset_index(drop=True)
    n = len(df_sorted)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train = df_sorted.iloc[:train_end]
    val = df_sorted.iloc[train_end:val_end]
    test = df_sorted.iloc[val_end:]

    X_train = train[available].fillna(0)
    y_train = train[PRICE_MODEL_TARGET]
    X_val = val[available].fillna(0)
    y_val = val[PRICE_MODEL_TARGET]
    X_test = test[available].fillna(0)
    y_test = test[PRICE_MODEL_TARGET]

    with mlflow.start_run(run_name="price_model_training") as run:
        mlflow.set_tag("model_type", "price_optimization")
        mlflow.set_tag("algorithm", "LightGBM")
        mlflow.log_param("n_features", len(available))
        mlflow.log_param("train_size", len(X_train))

        if tune:
            logger.info(f"Running RandomizedSearchCV ({n_iter} iterations)...")
            cv = TimeSeriesSplit(n_splits=3)
            base = lgb.LGBMRegressor(objective="regression", random_state=42, verbosity=-1)
            search = RandomizedSearchCV(
                base, PARAM_DISTRIBUTIONS, n_iter=n_iter, cv=cv,
                scoring="neg_root_mean_squared_error", n_jobs=-1,
                random_state=42, verbose=0,
            )
            search.fit(X_train, y_train)
            model = search.best_estimator_
            mlflow.log_params({f"best_{k}": v for k, v in search.best_params_.items()})
        else:
            model = lgb.LGBMRegressor(
                n_estimators=300, max_depth=5, learning_rate=0.05,
                num_leaves=31, min_child_samples=20,
                subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.1, reg_lambda=5.0,
                objective="regression", random_state=42, verbosity=-1,
            )
            model.fit(X_train, y_train)
            mlflow.log_params(model.get_params())

        # ── Metrics ──────────────────────────────────────────────────────
        test_preds = np.maximum(model.predict(X_test), 0)
        test_metrics = compute_metrics(y_test.values, test_preds)
        for k, v in test_metrics.items():
            mlflow.log_metric(f"test_{k}", v)

        # ── Price elasticity on test set ─────────────────────────────────
        elasticity = compute_price_elasticity(model, X_test)
        mlflow.log_metric("mean_price_elasticity", round(float(np.mean(elasticity)), 4))

        # ── Optimal price search on test set (sample for speed) ──────────
        sample_size = min(500, len(X_test))
        X_sample = X_test.iloc[:sample_size]
        cost_sample = test["cost_price"].fillna(test.get("base_cost_price", 0)).iloc[:sample_size].values

        opt_results = find_optimal_prices(model, X_sample, cost_sample)

        avg_profit_uplift = opt_results["expected_profit"].mean()
        mlflow.log_metric("avg_expected_profit", round(avg_profit_uplift, 2))

        # ── Register model ───────────────────────────────────────────────
        mlflow.lightgbm.log_model(
            model,
            artifact_path="price_model",
            registered_model_name=MODEL_NAME_PRICE,
        )

        logger.info(f"Test metrics: {test_metrics}")
        logger.info(f"Model registered as '{MODEL_NAME_PRICE}'")

    # Build full optimization results
    test_opt = test[["product_id", "store_id", "date"]].iloc[:sample_size].copy()
    test_opt = pd.concat([test_opt.reset_index(drop=True), opt_results], axis=1)

    return model, test_metrics, test_opt
