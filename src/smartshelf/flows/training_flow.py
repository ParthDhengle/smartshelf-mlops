"""
SmartShelf — Prefect Weekly Training Flow
==========================================
Replaces the legacy Airflow weekly_training_pipeline.py.
Handles the entire ML cycle natively in pure Python using Prefect.

Usage:
  # Run manually
  python src/smartshelf/flows/training_flow.py

  # Deploy to Prefect Server (Schedule for Sunday 4 AM)
  prefect deployment build src/smartshelf/flows/training_flow.py:weekly_training_flow -n weekly_train -q default --cron "0 4 * * 0"
"""

import ast
import json
import logging
import requests
from prefect import task, flow
from prefect.tasks import task_input_hash

# Set up simple logging (Prefect handles its own, but we keep this for console output)
logger = logging.getLogger(__name__)


@task(name="Build ML Features", retries=2, retry_delay_seconds=60)
def build_features_task():
    """Build the massive feature table from PostgreSQL for ML Models."""
    from smartshelf.pipelines.feature_engineering import build_features
    df = build_features()
    logger.info(f"Built feature matrix with {len(df)} rows.")
    return len(df)


@task(name="Train Tightly-Coupled Models", retries=1)
def train_all_models_task(feature_rows: int):
    """
    Run the full training pipeline in sequential order:
    Demand (XGBoost) -> Price (LightGBM) -> Inventory (XGBoost + EOQ).
    """
    if feature_rows == 0:
        logger.warning("No features generated. Skipping training.")
        return {}
        
    from smartshelf.pipelines.train_pipeline import run_training_pipeline
    
    # Run the pipeline natively
    results = run_training_pipeline(tune=True, auto_promote=True, rebuild_features=False)
    return results


@task(name="Push Prometheus Metrics")
def update_monitoring_metrics_task(results: dict):
    """Push the freshly evaluated model metrics into Grafana/Prometheus."""
    if not results:
        return
        
    from smartshelf.monitoring.metrics_collector import update_model_metrics
    
    for model_name in ["demand", "price", "inventory"]:
        if model_name in results:
            try:
                update_model_metrics(model_name, results[model_name])
                logger.info(f"Pushed {model_name} metrics to Prometheus.")
            except Exception as e:
                logger.error(f"Failed to push {model_name} metrics: {e}")


@task(name="Flush FastAPI Model Cache")
def clear_api_model_cache_task():
    """Trigger the live REST API to drop old models and pull the newly trained ones from MLflow."""
    try:
        resp = requests.post("http://localhost:8000/api/v1/admin/clear-cache", timeout=5)
        if resp.status_code == 200:
            logger.info("API model cache successfully cleared!")
        else:
            logger.warning(f"Cache clear returned status code {resp.status_code}")
    except Exception as e:
        logger.error(f"Could not reach API to clear cache (ensure uvicorn is running): {e}")


@flow(name="SmartShelf Weekly Training Pipeline", description="Sequential AI training using XGBoost and LightGBM.")
def weekly_training_flow():
    """The master flow executing the entire MLOps workflow."""
    
    # 1. Pipeline execution automatically constructs the DAG
    feature_count = build_features_task()
    
    # 2. Train Models (dependent upon features)
    results = train_all_models_task(feature_count)
    
    # 3. Parallel updates: metrics and caching
    update_monitoring_metrics_task(results)
    clear_api_model_cache_task()
    
    return results

if __name__ == "__main__":
    # Provides manual CLI trigger execution!
    weekly_training_flow()
