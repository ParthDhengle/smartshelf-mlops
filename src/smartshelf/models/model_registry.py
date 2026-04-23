"""
SmartShelf — MLflow Model Registry Helpers
==========================================
Utilities for managing the Staging → Production model lifecycle.

Key functions:
  - promote_model: Transition a model version to a new stage
  - get_production_model: Load the latest Production model by name
  - compare_and_promote: Auto-promote if new model beats current production
"""

import logging
from typing import Optional

import mlflow
from mlflow.tracking import MlflowClient

from smartshelf.config import MLFLOW_TRACKING_URI

logger = logging.getLogger(__name__)


def get_client() -> MlflowClient:
    """Get an MLflow tracking client."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    return MlflowClient()


def get_latest_model_version(model_name: str, stage: Optional[str] = None) -> Optional[int]:
    """
    Get the latest version number for a registered model.
    If stage is specified, returns latest version in that stage.
    """
    client = get_client()
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
        if not versions:
            return None

        if stage:
            # MLflow 3.x uses aliases instead of stages
            # Filter by alias matching the stage name
            for v in sorted(versions, key=lambda x: int(x.version), reverse=True):
                aliases = getattr(v, "aliases", [])
                if stage.lower() in [a.lower() for a in aliases]:
                    return int(v.version)
            return None

        # Return the highest version number
        return max(int(v.version) for v in versions)
    except Exception as e:
        logger.warning(f"Could not get model version for {model_name}: {e}")
        return None


def promote_model(model_name: str, version: int, stage: str = "production") -> None:
    """
    Promote a model version by setting an alias.
    MLflow 3.x uses aliases instead of stages.
    stage: 'staging' or 'production'
    """
    client = get_client()
    try:
        client.set_registered_model_alias(model_name, stage, str(version))
        logger.info(f"✅ {model_name} v{version} → {stage}")
    except Exception as e:
        logger.error(f"Failed to promote {model_name} v{version}: {e}")
        raise


def get_production_model(model_name: str):
    """
    Load the model currently aliased as 'production'.
    Falls back to the latest version if no production alias exists.
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    try:
        # Try loading by alias first (MLflow 3.x)
        model_uri = f"models:/{model_name}@production"
        model = mlflow.pyfunc.load_model(model_uri)
        logger.info(f"Loaded {model_name}@production")
        return model
    except Exception:
        # Fall back to latest version
        try:
            client = get_client()
            versions = client.search_model_versions(f"name='{model_name}'")
            if versions:
                latest = max(versions, key=lambda v: int(v.version))
                model_uri = f"models:/{model_name}/{latest.version}"
                model = mlflow.pyfunc.load_model(model_uri)
                logger.info(f"Loaded {model_name} v{latest.version} (latest)")
                return model
        except Exception as e:
            logger.error(f"Cannot load {model_name}: {e}")
    return None


def compare_and_promote(
    model_name: str,
    new_version: int,
    new_metrics: dict,
    metric_key: str = "rmse",
    lower_is_better: bool = True,
) -> bool:
    """
    Compare the new model version against the current production model.
    Auto-promote if the new model is better.

    Returns True if promoted, False otherwise.
    """
    client = get_client()

    # Get current production model's metrics
    try:
        prod_version = get_latest_model_version(model_name, stage="production")
        if prod_version is None:
            # No production model yet — promote the new one
            logger.info(f"No production model for {model_name}. Promoting v{new_version}.")
            promote_model(model_name, new_version, "production")
            return True

        # Get the run that produced the production model
        prod_model_version = client.get_model_version(model_name, str(prod_version))
        prod_run = client.get_run(prod_model_version.run_id)
        prod_metric = prod_run.data.metrics.get(f"test_{metric_key}")

        if prod_metric is None:
            logger.warning(f"No {metric_key} found for production model. Promoting new.")
            promote_model(model_name, new_version, "production")
            return True

        new_metric = new_metrics.get(metric_key)
        if new_metric is None:
            logger.warning(f"New model has no {metric_key}. Skipping promotion.")
            return False

        # Compare
        is_better = (new_metric < prod_metric) if lower_is_better else (new_metric > prod_metric)

        if is_better:
            logger.info(
                f"✅ New {model_name} v{new_version} ({metric_key}={new_metric}) "
                f"beats production v{prod_version} ({metric_key}={prod_metric}). Promoting."
            )
            promote_model(model_name, new_version, "production")
            return True
        else:
            logger.info(
                f"⏸️ New {model_name} v{new_version} ({metric_key}={new_metric}) "
                f"did NOT beat production v{prod_version} ({metric_key}={prod_metric}). Keeping current."
            )
            # Still mark as staging for review
            promote_model(model_name, new_version, "staging")
            return False

    except Exception as e:
        logger.error(f"Error during compare_and_promote: {e}")
        # Safe default: promote to staging
        promote_model(model_name, new_version, "staging")
        return False
