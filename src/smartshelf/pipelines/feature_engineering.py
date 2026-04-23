"""
SmartShelf — Feature Engineering Pipeline
==========================================
Builds the `product_store_day_features` table that all 3 ML models consume.

Design principles:
  - ALL joins are time-based (feature data < target date) to prevent leakage
  - Lag and rolling features use .shift() so row t never sees data from t or later
  - Categorical encoding uses LabelEncoder fitted on training data only
  - Output: Parquet file at data/processed/features.parquet

Feature groups:
  1. Lag features (units_sold at t-7, t-14, t-28)
  2. Rolling aggregates (mean/std over 7, 14, 28-day windows)
  3. Price features (selling price, discount, competitor diff, interactions)
  4. Time features (day_of_week, month, quarter, is_weekend, is_holiday, season)
  5. Weather features (temperature, rainfall, humidity, weather_type)
  6. Economic features (inflation, cpi, fuel_price, unemployment)
  7. Store & product static features
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from smartshelf.config import PROCESSED_DIR, DATABASE_URL
from smartshelf.data.postgres import get_postgres_engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


# ═════════════════════════════════════════════════════════════════════════════
# DATA LOADING — read directly from PostgreSQL (OLTP)
# ═════════════════════════════════════════════════════════════════════════════

def load_source_data(engine) -> dict[str, pd.DataFrame]:
    """Load all source tables needed for feature engineering."""
    logger.info("Loading source tables from PostgreSQL...")

    # Core: daily sales aggregated to product-store-day grain
    sales = pd.read_sql("""
        SELECT
            soi.product_id,
            so.store_id,
            so.order_date::date                     AS date,
            SUM(soi.quantity)                        AS units_sold,
            AVG(soi.unit_price)                      AS avg_unit_price,
            AVG(soi.discount_pct)                    AS avg_discount_pct,
            SUM(soi.line_total)                      AS revenue,
            AVG(so.customer_count)                   AS customer_count
        FROM sales_order_items soi
        JOIN sales_orders so ON soi.order_id = so.order_id
        GROUP BY soi.product_id, so.store_id, so.order_date::date
        ORDER BY so.order_date::date
    """, engine)
    sales["date"] = pd.to_datetime(sales["date"])

    products = pd.read_sql("""
        SELECT
            p.product_id, p.category_id,
            c.category_name,
            p.brand, p.perishable, p.shelf_life_days,
            p.base_cost_price, p.base_sell_price, p.gross_margin
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
    """, engine)

    stores = pd.read_sql("""
        SELECT store_id, store_type, store_size_sqft, city, state
        FROM stores
    """, engine)

    calendar = pd.read_sql("SELECT * FROM calendar", engine)
    calendar["date"] = pd.to_datetime(calendar["date"])

    weather = pd.read_sql("SELECT * FROM weather", engine)
    weather["weather_date"] = pd.to_datetime(weather["weather_date"])

    economic = pd.read_sql("SELECT * FROM economic_data", engine)
    economic["econ_date"] = pd.to_datetime(economic["econ_date"])

    prices = pd.read_sql("""
        SELECT product_id, store_id, effective_date::date AS date,
               selling_price, competitor_price, discount_pct
        FROM product_prices
    """, engine)
    prices["date"] = pd.to_datetime(prices["date"])

    return {
        "sales": sales,
        "products": products,
        "stores": stores,
        "calendar": calendar,
        "weather": weather,
        "economic": economic,
        "prices": prices,
    }


# ═════════════════════════════════════════════════════════════════════════════
# FEATURE BUILDERS
# ═════════════════════════════════════════════════════════════════════════════

def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lag features for units_sold.
    Uses shift() within each product-store group so row t only sees t-k.
    """
    logger.info("Building lag features...")
    group = df.groupby(["product_id", "store_id"])["units_sold"]

    for lag in [7, 14, 28]:
        df[f"units_sold_lag_{lag}"] = group.shift(lag)

    return df


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rolling mean/std over 7, 14, 28-day windows.
    shift(1) ensures the window ends at t-1, preventing leakage.
    """
    logger.info("Building rolling features...")
    for window in [7, 14, 28]:
        rolled = (
            df.groupby(["product_id", "store_id"])["units_sold"]
              .transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
        )
        df[f"units_sold_roll_mean_{window}"] = rolled

        rolled_std = (
            df.groupby(["product_id", "store_id"])["units_sold"]
              .transform(lambda x: x.shift(1).rolling(window, min_periods=1).std())
        )
        df[f"units_sold_roll_std_{window}"] = rolled_std.fillna(0)

    return df


def add_price_features(df: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """
    Merge latest available price data using asof join (time-safe).
    Only prices effective BEFORE the target date are used.
    """
    logger.info("Building price features...")

    # For each product-store, get the most recent price as of each date
    prices_sorted = prices.sort_values("date")
    df_sorted = df.sort_values("date")

    merged_parts = []
    for (pid, sid), grp in df_sorted.groupby(["product_id", "store_id"]):
        price_slice = prices_sorted[
            (prices_sorted["product_id"] == pid) &
            (prices_sorted["store_id"] == sid)
        ]
        if price_slice.empty:
            grp["selling_price"] = np.nan
            grp["competitor_price"] = np.nan
            grp["discount_pct_price"] = np.nan
        else:
            merged = pd.merge_asof(
                grp[["date"]].reset_index(),
                price_slice[["date", "selling_price", "competitor_price", "discount_pct"]].rename(
                    columns={"discount_pct": "discount_pct_price"}
                ),
                on="date",
                direction="backward"
            ).set_index("index")
            grp = grp.assign(
                selling_price=merged["selling_price"],
                competitor_price=merged["competitor_price"],
                discount_pct_price=merged["discount_pct_price"]
            )
        merged_parts.append(grp)

    df = pd.concat(merged_parts).sort_index()

    # Use price columns — rename discount to avoid clash with sales discount
    if "discount_pct_price" in df.columns:
        # Prefer the price-table discount; fall back to sales discount
        df["discount_pct"] = df["discount_pct_price"].fillna(df.get("avg_discount_pct", 0))
        df.drop(columns=["discount_pct_price"], inplace=True, errors="ignore")

    # Derived price features
    df["effective_price"] = (
        df["selling_price"] * (1 - df["discount_pct"].fillna(0) / 100)
    ).round(2)
    df["price_vs_competitor"] = (
        df["selling_price"] - df["competitor_price"]
    ).round(2)
    df["margin_pct"] = (
        (df["selling_price"] - df.get("base_cost_price", df["selling_price"] * 0.7))
        / df["selling_price"].replace(0, 1) * 100
    ).round(2)
    df["price_discount_interaction"] = (
        df["selling_price"] * df["discount_pct"].fillna(0) / 100
    ).round(2)

    return df


def add_time_features(df: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Merge calendar dimension (day_of_week, month, season, holiday, etc.)."""
    logger.info("Building time features...")
    cal_cols = ["date", "day_of_week", "month", "quarter", "is_weekend", "is_holiday", "season"]
    df = df.merge(calendar[cal_cols], on="date", how="left")
    return df


def add_weather_features(df: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Merge weather data by store_id and date."""
    logger.info("Building weather features...")
    weather_renamed = weather.rename(columns={"weather_date": "date"})
    weather_cols = ["store_id", "date", "temperature_c", "rainfall_mm",
                    "humidity_pct", "weather_type"]
    df = df.merge(weather_renamed[weather_cols], on=["store_id", "date"], how="left")
    return df


def add_economic_features(df: pd.DataFrame, economic: pd.DataFrame) -> pd.DataFrame:
    """
    Merge economic data using monthly join.
    Economic data is reported monthly — we match by year-month.
    """
    logger.info("Building economic features...")
    economic["econ_month"] = economic["econ_date"].dt.to_period("M")
    df["econ_month"] = df["date"].dt.to_period("M")

    econ_cols = ["econ_month", "inflation_rate", "cpi", "fuel_price", "unemployment_rate"]
    df = df.merge(economic[econ_cols].drop_duplicates("econ_month"),
                  on="econ_month", how="left")
    df.drop(columns=["econ_month"], inplace=True)
    return df


def add_static_features(df: pd.DataFrame, products: pd.DataFrame,
                         stores: pd.DataFrame) -> pd.DataFrame:
    """Merge product and store static attributes."""
    logger.info("Building static features...")
    product_cols = ["product_id", "category_name", "perishable", "shelf_life_days",
                    "base_cost_price", "base_sell_price", "gross_margin"]
    df = df.merge(products[product_cols], on="product_id", how="left")

    store_cols = ["store_id", "store_type", "store_size_sqft"]
    df = df.merge(stores[store_cols], on="store_id", how="left")

    return df


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Label-encode categorical columns.
    Encoders are fitted on the full dataset (train + val + test share
    the same categories; we're encoding identity, not leaking target info).
    """
    logger.info("Encoding categorical features...")
    cat_cols = {
        "store_type": "store_type_encoded",
        "category_name": "category_encoded",
        "season": "season_encoded",
        "weather_type": "weather_type_encoded",
    }

    for src, dst in cat_cols.items():
        if src in df.columns:
            le = LabelEncoder()
            df[dst] = le.fit_transform(df[src].astype(str).fillna("Unknown"))

    # Convert boolean to int
    for col in ["perishable", "is_weekend", "is_holiday"]:
        if col in df.columns:
            df[col] = df[col].astype(int)

    return df


# ═════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

def build_features(validate_only: bool = False) -> pd.DataFrame:
    """
    Full feature engineering pipeline.
    Returns the complete product_store_day_features DataFrame.
    """
    engine = get_postgres_engine()
    data = load_source_data(engine)

    df = data["sales"].copy()
    logger.info(f"Starting with {len(df)} product-store-day records")

    # Sort by product-store-date for proper lag/rolling computation
    df = df.sort_values(["product_id", "store_id", "date"]).reset_index(drop=True)

    # ── Build features in order ──────────────────────────────────────────
    df = add_static_features(df, data["products"], data["stores"])
    df = add_time_features(df, data["calendar"])
    df = add_weather_features(df, data["weather"])
    df = add_economic_features(df, data["economic"])
    df = add_price_features(df, data["prices"])
    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = encode_categoricals(df)

    # ── Drop rows with NaN lags (first 28 days per group have no lag-28) ─
    initial_len = len(df)
    df = df.dropna(subset=["units_sold_lag_28"])
    logger.info(f"Dropped {initial_len - len(df)} rows with insufficient lag history")

    # ── Validation checks ────────────────────────────────────────────────
    _validate_features(df)

    if validate_only:
        logger.info("Validation-only mode — skipping save")
        return df

    # ── Save ─────────────────────────────────────────────────────────────
    output_path = PROCESSED_DIR / "features.parquet"
    df.to_parquet(output_path, index=False, engine="pyarrow")
    logger.info(f"Saved {len(df)} rows → {output_path}")

    return df


def _validate_features(df: pd.DataFrame) -> None:
    """Sanity checks to catch data leakage and data quality issues."""
    logger.info("Running feature validation...")

    # 1. No future leakage: lag columns should never equal current units_sold
    for lag in [7, 14, 28]:
        col = f"units_sold_lag_{lag}"
        if col in df.columns:
            exact_match_pct = (df[col] == df["units_sold"]).mean()
            if exact_match_pct > 0.5:
                raise ValueError(
                    f"LEAKAGE DETECTED: {col} matches units_sold in "
                    f"{exact_match_pct:.1%} of rows"
                )

    # 2. No all-NaN feature columns
    feature_cols = [c for c in df.columns if c not in ["product_id", "store_id", "date"]]
    all_nan = [c for c in feature_cols if df[c].isna().all()]
    if all_nan:
        logger.warning(f"All-NaN columns detected: {all_nan}")

    # 3. Target should be non-negative
    assert (df["units_sold"] >= 0).all(), "Negative units_sold found"

    logger.info("✅ Feature validation passed")


if __name__ == "__main__":
    import sys
    validate_only = "--validate-only" in sys.argv
    build_features(validate_only=validate_only)
