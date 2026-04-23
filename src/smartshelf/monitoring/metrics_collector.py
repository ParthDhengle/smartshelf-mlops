"""
SmartShelf — Prometheus Metrics Collector
==========================================
Custom Prometheus metrics for ML model monitoring.

Exposed via the FastAPI /metrics endpoint and scraped by Prometheus.
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION METRICS
# ═════════════════════════════════════════════════════════════════════════════

# Request tracking (also set in main.py middleware, these are additional ML-specific)
PREDICTION_COUNT = Counter(
    "smartshelf_prediction_total",
    "Total predictions made",
    ["model_name", "endpoint"]
)

PREDICTION_LATENCY = Histogram(
    "smartshelf_prediction_latency_seconds",
    "Time to generate a single prediction",
    ["model_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# ═════════════════════════════════════════════════════════════════════════════
# MODEL PERFORMANCE METRICS
# ═════════════════════════════════════════════════════════════════════════════

MODEL_RMSE = Gauge(
    "smartshelf_model_rmse",
    "Current model RMSE (computed during training or evaluation)",
    ["model_name"]
)

MODEL_MAE = Gauge(
    "smartshelf_model_mae",
    "Current model MAE",
    ["model_name"]
)

MODEL_R2 = Gauge(
    "smartshelf_model_r2",
    "Current model R² score",
    ["model_name"]
)

# ═════════════════════════════════════════════════════════════════════════════
# DRIFT METRICS
# ═════════════════════════════════════════════════════════════════════════════

DRIFT_SCORE = Gauge(
    "smartshelf_drift_score",
    "Overall drift score (0-1). >0.3 triggers retraining.",
)

FEATURE_DRIFT_COUNT = Gauge(
    "smartshelf_features_drifted",
    "Number of features with PSI above threshold",
)

PREDICTION_DRIFT_PVALUE = Gauge(
    "smartshelf_prediction_drift_pvalue",
    "KS test p-value for prediction drift. <0.05 = significant.",
)

# ═════════════════════════════════════════════════════════════════════════════
# INVENTORY HEALTH
# ═════════════════════════════════════════════════════════════════════════════

STOCKOUT_RATE = Gauge(
    "smartshelf_stockout_rate",
    "Percentage of product-store combinations currently at zero stock",
)

REORDER_ALERTS = Gauge(
    "smartshelf_reorder_alerts",
    "Number of product-store pairs below reorder point",
)

# ═════════════════════════════════════════════════════════════════════════════
# TRAINING METRICS
# ═════════════════════════════════════════════════════════════════════════════

TRAINING_DURATION = Histogram(
    "smartshelf_training_duration_seconds",
    "Time taken for full training pipeline",
    buckets=[60, 120, 300, 600, 1200, 1800, 3600]
)

LAST_TRAINING_TIMESTAMP = Gauge(
    "smartshelf_last_training_timestamp",
    "Unix timestamp of the most recent training run",
)

# ═════════════════════════════════════════════════════════════════════════════
# MODEL INFO
# ═════════════════════════════════════════════════════════════════════════════

MODEL_INFO = Info(
    "smartshelf_model",
    "Model version and metadata",
)


# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def update_model_metrics(model_name: str, metrics: dict) -> None:
    """Update Prometheus gauges after training or evaluation."""
    if "rmse" in metrics:
        MODEL_RMSE.labels(model_name=model_name).set(metrics["rmse"])
    if "mae" in metrics:
        MODEL_MAE.labels(model_name=model_name).set(metrics["mae"])
    if "r2" in metrics:
        MODEL_R2.labels(model_name=model_name).set(metrics["r2"])


def update_drift_metrics(drift_report: dict) -> None:
    """Update Prometheus gauges from a drift detection report."""
    DRIFT_SCORE.set(drift_report.get("drift_score", 0))
    FEATURE_DRIFT_COUNT.set(drift_report.get("n_features_drifted", 0))

    pred_drift = drift_report.get("prediction_drift", {})
    PREDICTION_DRIFT_PVALUE.set(pred_drift.get("p_value", 1.0))


def record_prediction(model_name: str, endpoint: str, latency_seconds: float) -> None:
    """Record a prediction event for Prometheus."""
    PREDICTION_COUNT.labels(model_name=model_name, endpoint=endpoint).inc()
    PREDICTION_LATENCY.labels(model_name=model_name).observe(latency_seconds)


def update_inventory_health_metrics() -> None:
    """Compute and update inventory health metrics from database."""
    from smartshelf.api.dependencies import get_db_engine
    
    engine = get_db_engine()
    if engine is None:
        return
    
    try:
        # Calculate stockout rate
        stockout_query = """
        SELECT 
            COUNT(CASE WHEN i.stock_on_hand = 0 THEN 1 END) * 100.0 / COUNT(*) as stockout_rate
        FROM inventory i
        WHERE i.stock_on_hand IS NOT NULL
        """
        
        stockout_result = engine.execute(stockout_query).fetchone()
        if stockout_result:
            STOCKOUT_RATE.set(stockout_result[0] or 0)
        
        # Calculate reorder alerts (assuming reorder point is 10% of max stock for now)
        reorder_query = """
        SELECT COUNT(*) as reorder_alerts
        FROM inventory i
        WHERE i.stock_on_hand <= (i.max_stock_level * 0.1)
          AND i.stock_on_hand > 0
        """
        
        reorder_result = engine.execute(reorder_query).fetchone()
        if reorder_result:
            REORDER_ALERTS.set(reorder_result[0] or 0)
            
    except Exception as e:
        # Log error but don't crash
        import logging
        logging.error(f"Failed to update inventory health metrics: {e}")
