"""
SmartShelf — Inventory Optimization Model
==========================================
Hybrid EOQ (Economic Order Quantity) + ML approach.

How it works:
  1. EOQ formula for base order quantity:
       EOQ = √(2 × D × S / H)
       D = annual demand, S = ordering cost, H = holding cost per unit
  2. ML model predicts safety_stock adjustment based on:
     - Demand variability (from demand model)
     - Lead time variance (from supplier data)
     - Perishability
     - Weather/seasonal risk
  3. Reorder point = avg_daily_demand × lead_time + safety_stock

Uses demand + price model outputs as inputs (3rd model in the chain).
"""

import logging

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
import subprocess

# ── Hardware Safety ────────────────────────────────────────────────────────
try:
    HAS_GPU = subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
except Exception:
    HAS_GPU = False

DEVICE_XGB = "cuda" if HAS_GPU else "cpu"
N_JOBS_CV = 2 if HAS_GPU else 1  
N_JOBS_MODEL = -1 if HAS_GPU else 2  

from smartshelf.config import (
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MODEL_NAME_INVENTORY,
)
from smartshelf.data.postgres import get_postgres_engine

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# EOQ CALCULATION (DETERMINISTIC COMPONENT)
# ═════════════════════════════════════════════════════════════════════════════

def compute_eoq(annual_demand: float, ordering_cost: float,
                holding_cost_per_unit: float) -> float:
    """
    Classic EOQ formula.
    Args:
        annual_demand: total units demanded per year
        ordering_cost: fixed cost per purchase order (delivery_cost from supplier)
        holding_cost_per_unit: annual cost to hold 1 unit (≈ 20-25% of unit cost)
    """
    if annual_demand <= 0 or ordering_cost <= 0 or holding_cost_per_unit <= 0:
        return 0
    return np.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)


# ═════════════════════════════════════════════════════════════════════════════
# FEATURE PREPARATION
# ═════════════════════════════════════════════════════════════════════════════

INVENTORY_FEATURES = [
    "predicted_demand",        # from demand model
    "demand_std",              # rolling std of demand
    "optimal_price",           # from price model
    "lead_time_days",          # from supplier
    "lead_time_variance",      # from purchase history
    "perishable",
    "shelf_life_days",
    "store_size_sqft",
    "units_sold_roll_mean_7",
    "units_sold_roll_mean_28",
    "units_sold_roll_std_28",
    "cost_price",
    "delivery_cost",
    "reliability_score",
    "season_encoded",
    "category_encoded",
]


def prepare_inventory_features(
    features_df: pd.DataFrame,
    demand_preds: pd.DataFrame,
    price_preds: pd.DataFrame,
) -> pd.DataFrame:
    """
    Enrich the feature table with:
      - demand model predictions
      - price model predictions
      - supplier lead time data
      - historical demand volatility

    This is the final merge step before the inventory model trains.
    """
    engine = get_postgres_engine()
    df = features_df.copy()

    # Merge demand predictions if not already present
    if "predicted_demand" not in df.columns:
        df = df.merge(
            demand_preds[["product_id", "store_id", "date", "predicted_demand"]],
            on=["product_id", "store_id", "date"],
            how="left"
        )
        df["predicted_demand"] = df["predicted_demand"].fillna(0)

    # Merge price predictions if not already present
    if "optimal_price" not in df.columns:
        if price_preds is not None and not price_preds.empty:
            df = df.merge(
                price_preds[["product_id", "store_id", "date", "optimal_price"]],
                on=["product_id", "store_id", "date"],
                how="left"
            )
            df["optimal_price"] = df["optimal_price"].fillna(df.get("selling_price", 0))
        else:
            df["optimal_price"] = df.get("selling_price", 0)

    # Demand volatility
    df["demand_std"] = df.get("units_sold_roll_std_28", 0)

    # Supplier data
    supplier_data = pd.read_sql("""
        SELECT
            ps.product_id,
            s.lead_time_days,
            s.delivery_cost,
            s.reliability_score
        FROM product_suppliers ps
        JOIN suppliers s ON ps.supplier_id = s.supplier_id
    """, engine)
    # If multiple suppliers per product, take the primary (lowest cost)
    supplier_data = supplier_data.sort_values("delivery_cost").drop_duplicates("product_id")
    df = df.merge(supplier_data, on="product_id", how="left")

    # Lead time variance from purchase order history
    lt_variance = pd.read_sql("""
        SELECT
            poi.product_id,
            STDDEV(po.expected_delivery - po.order_date) AS lead_time_variance
        FROM purchase_order_items poi
        JOIN purchase_orders po ON poi.po_id = po.po_id
        WHERE po.status = 'DELIVERED'
        GROUP BY poi.product_id
    """, engine)
    df = df.merge(lt_variance, on="product_id", how="left")
    df["lead_time_variance"] = df["lead_time_variance"].fillna(0)

    # Cost price (for EOQ holding cost calculation)
    if "cost_price" not in df.columns:
        df["cost_price"] = df.get("base_cost_price", 0)

    return df


# ═════════════════════════════════════════════════════════════════════════════
# SAFETY STOCK ML MODEL
# ═════════════════════════════════════════════════════════════════════════════

def compute_target_safety_stock(df: pd.DataFrame) -> pd.Series:
    """
    Compute the 'ideal' safety stock as a training target.
    Uses the service-level formula:
        safety_stock = z × σ_demand × √(lead_time)
    where z = 1.65 for 95% service level.
    """
    z = 1.65  # 95% service level
    demand_std = df["demand_std"].fillna(0).clip(lower=0)
    lead_time = df["lead_time_days"].fillna(3).clip(lower=1)
    return (z * demand_std * np.sqrt(lead_time)).round(0).astype(int)


PARAM_DISTRIBUTIONS = {
    "n_estimators": [100, 200, 300],
    "max_depth": [3, 4, 5],
    "learning_rate": [0.01, 0.05, 0.1],
    "min_child_weight": [5, 10, 20],
    "subsample": [0.7, 0.8],
    "colsample_bytree": [0.7, 0.8],
    "reg_alpha": [0, 0.1, 1.0],
    "reg_lambda": [1.0, 5.0],
}


def train_inventory_model(
    df: pd.DataFrame,
    tune: bool = True,
    n_iter: int = 15,
) -> tuple[xgb.XGBRegressor, dict, pd.DataFrame]:
    """
    Train the safety stock prediction model and compute full inventory plan.

    Returns:
        (model, test_metrics, inventory_plan_df)
        inventory_plan_df columns:
            product_id, store_id, date, reorder_point, safety_stock,
            order_qty (EOQ), predicted_demand
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    # Compute target
    df["target_safety_stock"] = compute_target_safety_stock(df)

    available = [f for f in INVENTORY_FEATURES if f in df.columns]

    # Time-based split
    df_sorted = df.sort_values("date").reset_index(drop=True)
    n = len(df_sorted)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train = df_sorted.iloc[:train_end]
    val = df_sorted.iloc[train_end:val_end]
    test = df_sorted.iloc[val_end:]

    X_train = train[available].fillna(0)
    y_train = train["target_safety_stock"]
    X_val = val[available].fillna(0)
    y_val = val["target_safety_stock"]
    X_test = test[available].fillna(0)
    y_test = test["target_safety_stock"]

    with mlflow.start_run(run_name="inventory_model_training") as run:
        mlflow.set_tag("model_type", "inventory_optimization")
        mlflow.set_tag("algorithm", "XGBoost + EOQ Hybrid")
        mlflow.log_param("n_features", len(available))

        if tune:
            logger.info(f"Tuning inventory model ({n_iter} iters)...")
            cv = TimeSeriesSplit(n_splits=3)
            base = xgb.XGBRegressor(
                objective="reg:squarederror", tree_method="hist",
                device=DEVICE_XGB, n_jobs=N_JOBS_MODEL,
                random_state=42, early_stopping_rounds=15,
            )
            search = RandomizedSearchCV(
                base, PARAM_DISTRIBUTIONS, n_iter=n_iter, cv=cv,
                scoring="neg_root_mean_squared_error", n_jobs=N_JOBS_CV,
                random_state=42, verbose=0,
            )
            search.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
            model = search.best_estimator_
            mlflow.log_params({f"best_{k}": v for k, v in search.best_params_.items()})
        else:
            model = xgb.XGBRegressor(
                n_estimators=200, max_depth=4, learning_rate=0.05,
                min_child_weight=10, subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.1, reg_lambda=5.0,
                objective="reg:squarederror", tree_method="hist",
                device=DEVICE_XGB, n_jobs=N_JOBS_MODEL,
                early_stopping_rounds=15, random_state=42,
            )
            model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        # ── Evaluate ─────────────────────────────────────────────────────
        test_preds = np.maximum(model.predict(X_test), 0).round(0).astype(int)
        rmse = np.sqrt(mean_squared_error(y_test, test_preds))
        mae = mean_absolute_error(y_test, test_preds)
        r2 = r2_score(y_test, test_preds)
        test_metrics = {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4)}

        for k, v in test_metrics.items():
            mlflow.log_metric(f"test_{k}", v)

        # ── Build inventory plan ─────────────────────────────────────────
        plan = test[["product_id", "store_id", "date"]].copy()
        plan["safety_stock"] = test_preds
        plan["predicted_demand"] = test["predicted_demand"].fillna(0).values
        plan["lead_time_days"] = test["lead_time_days"].fillna(3).values
        plan["cost_price"] = test["cost_price"].fillna(0).values
        plan["delivery_cost"] = test["delivery_cost"].fillna(50).values

        # Reorder point = avg_daily_demand × lead_time + safety_stock
        plan["avg_daily_demand"] = plan["predicted_demand"].clip(lower=0)
        plan["reorder_point"] = (
            plan["avg_daily_demand"] * plan["lead_time_days"] + plan["safety_stock"]
        ).round(0).astype(int)

        # EOQ for order quantity
        holding_cost_rate = 0.25  # 25% of unit cost per year
        plan["order_qty"] = plan.apply(
            lambda row: round(compute_eoq(
                annual_demand=row["avg_daily_demand"] * 365,
                ordering_cost=row["delivery_cost"],
                holding_cost_per_unit=row["cost_price"] * holding_cost_rate + 0.01,
            )),
            axis=1
        ).astype(int)

        # ── Register model ───────────────────────────────────────────────
        mlflow.xgboost.log_model(
            model,
            artifact_path="inventory_model",
            registered_model_name=MODEL_NAME_INVENTORY,
        )

        logger.info(f"Test metrics: {test_metrics}")
        logger.info(f"Model registered as '{MODEL_NAME_INVENTORY}'")

    return model, test_metrics, plan[[
        "product_id", "store_id", "date",
        "reorder_point", "safety_stock", "order_qty",
        "predicted_demand", "avg_daily_demand"
    ]]
