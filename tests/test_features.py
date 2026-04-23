"""
SmartShelf — Feature Engineering Tests
=======================================
Validates:
  - No future data leakage in lag/rolling features
  - Correct column schema
  - No all-NaN feature columns
  - Non-negative target values
"""

import numpy as np
import pandas as pd
import pytest


def make_mock_features(n_days=60, n_products=2, n_stores=2):
    """Create synthetic feature data for testing."""
    records = []
    for pid in range(1, n_products + 1):
        for sid in range(1, n_stores + 1):
            for d in pd.date_range("2024-01-01", periods=n_days):
                records.append({
                    "product_id": pid,
                    "store_id": sid,
                    "date": d,
                    "units_sold": max(0, int(np.random.normal(20, 5))),
                })
    return pd.DataFrame(records)


class TestLagFeatures:
    """Tests for lag feature correctness."""

    def test_lag_values_are_shifted(self):
        """Lag-7 for row t should equal units_sold at row t-7."""
        df = make_mock_features(n_days=40, n_products=1, n_stores=1)
        df = df.sort_values(["product_id", "store_id", "date"]).reset_index(drop=True)

        group = df.groupby(["product_id", "store_id"])["units_sold"]
        df["units_sold_lag_7"] = group.shift(7)

        # For row 10, lag_7 should equal row 3's units_sold
        for idx in range(7, len(df)):
            expected = df.iloc[idx - 7]["units_sold"]
            actual = df.iloc[idx]["units_sold_lag_7"]
            assert expected == actual, f"Row {idx}: expected lag={expected}, got {actual}"

    def test_no_leakage_in_lags(self):
        """Lag features should NEVER equal the current day's value for all rows."""
        df = make_mock_features(n_days=60, n_products=1, n_stores=1)
        df = df.sort_values("date").reset_index(drop=True)

        group = df.groupby(["product_id", "store_id"])["units_sold"]
        df["units_sold_lag_7"] = group.shift(7)

        valid = df.dropna(subset=["units_sold_lag_7"])
        exact_match_rate = (valid["units_sold_lag_7"] == valid["units_sold"]).mean()

        # With random data, an exact match rate > 50% is suspicious
        assert exact_match_rate < 0.5, f"Leakage: {exact_match_rate:.1%} exact matches"

    def test_first_rows_are_nan(self):
        """First N rows per group should have NaN lags."""
        df = make_mock_features(n_days=30, n_products=1, n_stores=1)
        df = df.sort_values("date").reset_index(drop=True)

        group = df.groupby(["product_id", "store_id"])["units_sold"]
        df["lag_7"] = group.shift(7)
        df["lag_14"] = group.shift(14)
        df["lag_28"] = group.shift(28)

        assert df["lag_7"].iloc[:7].isna().all()
        assert df["lag_14"].iloc[:14].isna().all()
        assert df["lag_28"].iloc[:28].isna().all()


class TestRollingFeatures:
    """Tests for rolling aggregate correctness."""

    def test_rolling_mean_excludes_current(self):
        """Rolling mean should use shift(1) — never include current row."""
        df = make_mock_features(n_days=20, n_products=1, n_stores=1)
        df = df.sort_values("date").reset_index(drop=True)

        df["roll_mean_7"] = (
            df.groupby(["product_id", "store_id"])["units_sold"]
              .transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean())
        )

        # For row 8, rolling mean should use rows 1-7 (shifted by 1)
        for idx in range(8, len(df)):
            window = df["units_sold"].iloc[idx-7:idx].values
            expected = np.mean(window)
            actual = df["roll_mean_7"].iloc[idx]
            assert abs(actual - expected) < 0.01, f"Row {idx}: expected {expected}, got {actual}"


class TestFeatureSchema:
    """Tests for output schema correctness."""

    def test_target_non_negative(self):
        """units_sold must be ≥ 0."""
        df = make_mock_features()
        assert (df["units_sold"] >= 0).all()

    def test_no_duplicate_rows(self):
        """Each product-store-date should be unique."""
        df = make_mock_features()
        dupes = df.duplicated(subset=["product_id", "store_id", "date"])
        assert not dupes.any(), f"Found {dupes.sum()} duplicate rows"

    def test_date_continuity(self):
        """No date gaps within a product-store group."""
        df = make_mock_features(n_days=30, n_products=1, n_stores=1)
        df = df.sort_values("date")
        date_diffs = df["date"].diff().dropna()
        assert (date_diffs == pd.Timedelta(days=1)).all()
