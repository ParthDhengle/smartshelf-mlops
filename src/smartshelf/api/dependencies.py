"""
SmartShelf — API Dependencies
==============================
Shared dependencies injected into FastAPI route handlers.
Handles model loading (cached), DB sessions, and health checks.
"""

import logging
from functools import lru_cache
from typing import Optional

import mlflow
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from smartshelf.config import (
    DATABASE_URL,
    MLFLOW_TRACKING_URI,
    MODEL_NAME_DEMAND,
    MODEL_NAME_PRICE,
    MODEL_NAME_INVENTORY,
)

logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

_engine: Optional[Engine] = None


def get_db_engine() -> Engine:
    """Get or create the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
    return _engine


def check_db_connection() -> bool:
    """Test database connectivity."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
# MODEL LOADING
# ═════════════════════════════════════════════════════════════════════════════

# Cache for loaded models — avoids reloading on every request
_model_cache: dict = {}


def load_model(model_name: str):
    """
    Load a model from MLflow registry.
    Tries: @production alias → latest version → None.
    Results are cached in memory.
    """
    if model_name in _model_cache:
        return _model_cache[model_name]

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # Try production alias first
    for uri_pattern in [
        f"models:/{model_name}@production",
        f"models:/{model_name}@staging",
    ]:
        try:
            model = mlflow.pyfunc.load_model(uri_pattern)
            _model_cache[model_name] = model
            logger.info(f"Loaded {model_name} from {uri_pattern}")
            return model
        except Exception:
            continue

    # Fall back to latest version
    try:
        client = mlflow.MlflowClient()
        versions = client.search_model_versions(f"name='{model_name}'")
        if versions:
            latest = max(versions, key=lambda v: int(v.version))
            model = mlflow.pyfunc.load_model(f"models:/{model_name}/{latest.version}")
            _model_cache[model_name] = model
            logger.info(f"Loaded {model_name} v{latest.version} (latest)")
            return model
    except Exception as e:
        logger.error(f"Cannot load {model_name}: {e}")

    return None


def get_demand_model():
    """Get the demand forecasting model."""
    return load_model(MODEL_NAME_DEMAND)


def get_price_model():
    """Get the price optimization model."""
    return load_model(MODEL_NAME_PRICE)


def get_inventory_model():
    """Get the inventory optimization model."""
    return load_model(MODEL_NAME_INVENTORY)


def clear_model_cache():
    """Force reload models on next request (used after retraining)."""
    global _model_cache
    _model_cache = {}
    logger.info("Model cache cleared")


def check_mlflow_connection() -> bool:
    """Test MLflow connectivity."""
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.MlflowClient()
        client.search_experiments()
        return True
    except Exception as e:
        logger.error(f"MLflow connection failed: {e}")
        return False


def get_loaded_models_status() -> dict:
    """Check which models are currently loaded."""
    return {
        MODEL_NAME_DEMAND: MODEL_NAME_DEMAND in _model_cache,
        MODEL_NAME_PRICE: MODEL_NAME_PRICE in _model_cache,
        MODEL_NAME_INVENTORY: MODEL_NAME_INVENTORY in _model_cache,
    }


# ═════════════════════════════════════════════════════════════════════════════
# DATA HELPERS (for API endpoints that need DB queries)
# ═════════════════════════════════════════════════════════════════════════════

def get_product_info(product_id: int) -> Optional[dict]:
    """Fetch product details from OLTP."""
    engine = get_db_engine()
    df = pd.read_sql(
        f"""
        SELECT p.*, c.category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
        WHERE p.product_id = {product_id}
        """,
        engine
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_store_info(store_id: int) -> Optional[dict]:
    """Fetch store details from OLTP."""
    engine = get_db_engine()
    df = pd.read_sql(f"SELECT * FROM stores WHERE store_id = {store_id}", engine)
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_current_inventory(product_id: int, store_id: int) -> Optional[dict]:
    """Fetch current inventory levels."""
    engine = get_db_engine()
    df = pd.read_sql(
        f"""
        SELECT * FROM inventory
        WHERE product_id = {product_id} AND store_id = {store_id}
        """,
        engine
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()
