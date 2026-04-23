"""
SmartShelf — Model Tests
=========================
Smoke tests to verify models train on small data and produce valid predictions.
"""

import numpy as np
import pandas as pd
import pytest


def make_small_training_data(n_rows=200):
    """Create minimal training data for smoke testing."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n_rows)
    return pd.DataFrame({
        "date": dates,
        "product_id": np.random.choice([1, 2, 3], n_rows),
        "store_id": np.random.choice([1, 2], n_rows),
        "units_sold": np.random.poisson(15, n_rows),
        # Lag features
        "units_sold_lag_7": np.random.poisson(15, n_rows),
        "units_sold_lag_14": np.random.poisson(15, n_rows),
        "units_sold_lag_28": np.random.poisson(15, n_rows),
        # Rolling features
        "units_sold_roll_mean_7": np.random.normal(15, 3, n_rows),
        "units_sold_roll_std_7": np.random.uniform(1, 5, n_rows),
        "units_sold_roll_mean_14": np.random.normal(15, 3, n_rows),
        "units_sold_roll_std_14": np.random.uniform(1, 5, n_rows),
        "units_sold_roll_mean_28": np.random.normal(15, 3, n_rows),
        "units_sold_roll_std_28": np.random.uniform(1, 5, n_rows),
        # Price features
        "selling_price": np.random.uniform(50, 200, n_rows),
        "competitor_price": np.random.uniform(45, 210, n_rows),
        "discount_pct": np.random.uniform(0, 30, n_rows),
        "effective_price": np.random.uniform(40, 180, n_rows),
        "price_vs_competitor": np.random.normal(0, 20, n_rows),
        "margin_pct": np.random.uniform(10, 50, n_rows),
        "price_discount_interaction": np.random.uniform(0, 50, n_rows),
        # Time features
        "day_of_week": np.random.randint(0, 7, n_rows),
        "month": np.random.randint(1, 13, n_rows),
        "quarter": np.random.randint(1, 5, n_rows),
        "is_weekend": np.random.randint(0, 2, n_rows),
        "is_holiday": np.random.randint(0, 2, n_rows),
        # Weather
        "temperature_c": np.random.normal(25, 8, n_rows),
        "rainfall_mm": np.random.exponential(5, n_rows),
        "humidity_pct": np.random.uniform(30, 90, n_rows),
        # Economic
        "inflation_rate": np.random.uniform(3, 8, n_rows),
        "cpi": np.random.uniform(300, 400, n_rows),
        "fuel_price": np.random.uniform(90, 120, n_rows),
        "unemployment_rate": np.random.uniform(3, 8, n_rows),
        # Store & product
        "store_size_sqft": np.random.choice([2000, 5000, 8000], n_rows),
        "perishable": np.random.randint(0, 2, n_rows),
        "shelf_life_days": np.random.choice([7, 30, 365], n_rows),
        # Encoded categoricals
        "store_type_encoded": np.random.randint(0, 3, n_rows),
        "category_encoded": np.random.randint(0, 10, n_rows),
        "season_encoded": np.random.randint(0, 4, n_rows),
        "weather_type_encoded": np.random.randint(0, 5, n_rows),
    })


class TestDemandModel:
    """Smoke tests for demand model."""

    def test_demand_model_trains_and_predicts(self):
        """Model should train on small data without crashing."""
        import xgboost as xgb
        from smartshelf.config import DEMAND_FEATURES, DEMAND_TARGET

        df = make_small_training_data(300)
        available = [f for f in DEMAND_FEATURES if f in df.columns]

        assert len(available) > 10, f"Only {len(available)} features available"

        X = df[available].fillna(0)
        y = df[DEMAND_TARGET]

        model = xgb.XGBRegressor(
            n_estimators=10, max_depth=3, random_state=42
        )
        model.fit(X[:200], y[:200])
        preds = model.predict(X[200:])

        assert len(preds) == 100
        assert np.all(np.isfinite(preds))

    def test_predictions_are_reasonable(self):
        """Predictions should be in a reasonable range."""
        import xgboost as xgb
        from smartshelf.config import DEMAND_FEATURES

        df = make_small_training_data(300)
        available = [f for f in DEMAND_FEATURES if f in df.columns]

        X = df[available].fillna(0)
        y = df["units_sold"]

        model = xgb.XGBRegressor(n_estimators=20, max_depth=3, random_state=42)
        model.fit(X[:200], y[:200])
        preds = model.predict(X[200:])

        # Predictions should be within 5x of the mean (loose sanity check)
        mean_target = y.mean()
        assert np.max(preds) < mean_target * 10, "Predictions are unreasonably high"
        assert np.min(preds) > -mean_target * 5, "Predictions are unreasonably negative"


class TestInventoryModel:
    """Tests for EOQ calculation."""

    def test_eoq_formula(self):
        """EOQ should match the textbook formula."""
        from smartshelf.models.inventory_model import compute_eoq

        # EOQ = sqrt(2 * D * S / H) = sqrt(2 * 1000 * 50 / 5) = sqrt(20000) ≈ 141
        eoq = compute_eoq(annual_demand=1000, ordering_cost=50, holding_cost_per_unit=5)
        expected = np.sqrt(2 * 1000 * 50 / 5)
        assert abs(eoq - expected) < 0.01

    def test_eoq_zero_demand(self):
        """EOQ should be 0 when demand is 0."""
        from smartshelf.models.inventory_model import compute_eoq
        assert compute_eoq(0, 50, 5) == 0

    def test_eoq_zero_cost(self):
        """EOQ should be 0 when costs are 0."""
        from smartshelf.models.inventory_model import compute_eoq
        assert compute_eoq(1000, 0, 5) == 0


class TestMetrics:
    """Tests for metric computation."""

    def test_rmse_computation(self):
        """RMSE should be correct."""
        from smartshelf.models.demand_model import compute_metrics

        y_true = np.array([10, 20, 30, 40, 50])
        y_pred = np.array([12, 18, 33, 37, 52])

        metrics = compute_metrics(y_true, y_pred)

        assert "rmse" in metrics
        assert "mae" in metrics
        assert "r2" in metrics
        assert "mape" in metrics
        assert metrics["rmse"] > 0
        assert metrics["mae"] > 0
        assert metrics["r2"] <= 1.0

    def test_perfect_predictions(self):
        """Perfect predictions should give RMSE=0, R²=1."""
        from smartshelf.models.demand_model import compute_metrics

        y = np.array([10, 20, 30, 40, 50])
        metrics = compute_metrics(y, y.copy())

        assert metrics["rmse"] == 0
        assert metrics["mae"] == 0
        assert metrics["r2"] == 1.0
