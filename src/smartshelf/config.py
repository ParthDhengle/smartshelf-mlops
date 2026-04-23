"""
SmartShelf — Centralized Configuration
=======================================
Single source of truth for all environment-dependent settings.
Loaded from .env with sensible defaults for local development.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env from project root ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/smartshelf → project root
load_dotenv(PROJECT_ROOT / ".env")

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DRIFT_REPORTS_DIR = DATA_DIR / "drift_reports"

# Ensure directories exist
for d in [PROCESSED_DIR, DRIFT_REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── PostgreSQL ───────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1246@localhost:5432/smartshelf")

# ── BigQuery ─────────────────────────────────────────────────────────────────
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "smartshelf-493319")
BQ_DATASET = os.getenv("BQ_DATASET", "smartshelf_1st_dataset")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# ── MLflow ───────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "smartshelf")

# ── Model Names in MLflow Registry ──────────────────────────────────────────
MODEL_NAME_DEMAND = "Demand_Model"
MODEL_NAME_PRICE = "Price_Model"
MODEL_NAME_INVENTORY = "Inventory_Model"

# ── Feature Lists ────────────────────────────────────────────────────────────
# These define which columns the models consume at training and inference time.
# Kept here so training + API share the exact same schema.

DEMAND_FEATURES = [
    # Lag features
    "units_sold_lag_7", "units_sold_lag_14", "units_sold_lag_28",
    # Rolling features
    "units_sold_roll_mean_7", "units_sold_roll_std_7",
    "units_sold_roll_mean_14", "units_sold_roll_std_14",
    "units_sold_roll_mean_28", "units_sold_roll_std_28",
    # Price features
    "selling_price", "competitor_price", "discount_pct",
    "effective_price", "price_vs_competitor", "margin_pct",
    "price_discount_interaction",
    # Time features
    "day_of_week", "month", "quarter", "is_weekend", "is_holiday",
    # Weather features
    "temperature_c", "rainfall_mm", "humidity_pct",
    # Economic features
    "inflation_rate", "cpi", "fuel_price", "unemployment_rate",
    # Store features
    "store_size_sqft",
    # Product features
    "perishable", "shelf_life_days",
    # Encoded categoricals
    "store_type_encoded", "category_encoded", "season_encoded",
    "weather_type_encoded",
]

DEMAND_TARGET = "units_sold"

PRICE_FEATURES = DEMAND_FEATURES + [
    "predicted_demand",
    "cost_price",
    "base_sell_price",
    "gross_margin",
]

PRICE_TARGET = "optimal_price"

# ── Drift Detection Thresholds ──────────────────────────────────────────────
PSI_THRESHOLD = 0.2         # Population Stability Index — >0.2 = significant drift
KS_THRESHOLD = 0.05         # KS test p-value — <0.05 = prediction drift
DRIFT_LOOKBACK_DAYS = 30    # Number of days of recent data to compare against training

# ── API ──────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── Prefect ──────────────────────────────────────────────────────────────────
# Orchestration relies natively on pure python within src/smartshelf/flows/
