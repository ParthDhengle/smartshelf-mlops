"""
SmartShelf — Training Pipeline Orchestrator
============================================
Runs the full training chain in dependency order:

    Features → Demand Model → Price Model → Inventory Model → Profit

This is the single entry point for both manual runs and Airflow DAGs.
It handles the data flow between dependent models:
  1. Build features
  2. Train demand model → produce demand predictions
  3. Inject demand preds into features → train price model → produce price preds
  4. Inject demand + price preds → train inventory model → produce inventory plan
  5. Save all results
"""

import logging
from datetime import datetime

import pandas as pd

from smartshelf.config import PROCESSED_DIR, MODEL_NAME_DEMAND, MODEL_NAME_PRICE, MODEL_NAME_INVENTORY
from smartshelf.models.demand_model import train_demand_model
from smartshelf.models.price_model import train_price_model
from smartshelf.models.inventory_model import (
    prepare_inventory_features,
    train_inventory_model,
)
from smartshelf.models.model_registry import compare_and_promote, get_latest_model_version
from smartshelf.pipelines.feature_engineering import build_features

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def run_training_pipeline(
    tune: bool = True,
    auto_promote: bool = True,
    rebuild_features: bool = True,
) -> dict:
    """
    Full training pipeline.

    Args:
        tune: Whether to run hyperparameter tuning (slower but better).
        auto_promote: Whether to auto-promote models if they beat production.
        rebuild_features: Whether to rebuild features from scratch or load cached.

    Returns:
        dict with metrics and results for each model.
    """
    start_time = datetime.now()
    results = {}

    # ── Step 1: Feature Engineering ─────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1/4: Building features")
    logger.info("=" * 60)

    if rebuild_features:
        features = build_features()
    else:
        features_path = PROCESSED_DIR / "features.parquet"
        if features_path.exists():
            features = pd.read_parquet(features_path)
            logger.info(f"Loaded cached features: {len(features)} rows")
        else:
            features = build_features()

    results["feature_rows"] = len(features)

    # ── Step 2: Train Demand Model ──────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2/4: Training Demand Model")
    logger.info("=" * 60)

    demand_model, demand_metrics, demand_preds = train_demand_model(features, tune=tune)
    results["demand"] = demand_metrics

    # Inject demand predictions back into the full feature set
    # Use the model to predict on ALL data (for downstream model training)
    # IMPORTANT: Use the model's feature_names order (training order), NOT DataFrame column order
    model_feature_names = demand_model.get_booster().feature_names
    available_demand_features = [f for f in model_feature_names if f in features.columns]
    if not available_demand_features:
        from smartshelf.config import DEMAND_FEATURES
        available_demand_features = [f for f in DEMAND_FEATURES if f in features.columns]

    features["predicted_demand"] = demand_model.predict(
        features[available_demand_features].fillna(0)
    ).clip(min=0)

    logger.info(f"Demand metrics: {demand_metrics}")

    # ── Step 3: Train Price Model ───────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 3/4: Training Price Model")
    logger.info("=" * 60)

    # Ensure cost_price is available
    if "cost_price" not in features.columns and "base_cost_price" in features.columns:
        features["cost_price"] = features["base_cost_price"]

    price_model, price_metrics, price_preds = train_price_model(features, tune=tune)
    results["price"] = price_metrics

    logger.info(f"Price metrics: {price_metrics}")

    # ── Step 4: Train Inventory Model ───────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4/4: Training Inventory Model")
    logger.info("=" * 60)

    inv_features = prepare_inventory_features(features, demand_preds, price_preds)
    inv_model, inv_metrics, inv_plan = train_inventory_model(inv_features, tune=tune)
    results["inventory"] = inv_metrics

    logger.info(f"Inventory metrics: {inv_metrics}")

    # ── Auto-promote models ─────────────────────────────────────────────
    if auto_promote:
        logger.info("Checking model promotion...")
        for model_name, metrics in [
            (MODEL_NAME_DEMAND, demand_metrics),
            (MODEL_NAME_PRICE, price_metrics),
            (MODEL_NAME_INVENTORY, inv_metrics),
        ]:
            version = get_latest_model_version(model_name)
            if version is not None:
                compare_and_promote(model_name, version, metrics, metric_key="rmse")

    # ── Save results ────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    demand_preds.to_parquet(PROCESSED_DIR / f"demand_predictions_{timestamp}.parquet", index=False)
    price_preds.to_parquet(PROCESSED_DIR / f"price_predictions_{timestamp}.parquet", index=False)
    inv_plan.to_parquet(PROCESSED_DIR / f"inventory_plan_{timestamp}.parquet", index=False)

    elapsed = (datetime.now() - start_time).total_seconds()
    results["elapsed_seconds"] = round(elapsed, 1)

    logger.info("=" * 60)
    logger.info(f"🏁 Training pipeline complete in {elapsed:.0f}s")
    logger.info(f"Results: {results}")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    run_training_pipeline(tune=True, auto_promote=True, rebuild_features=True)
