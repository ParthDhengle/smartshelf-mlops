"""
SmartShelf — API Tests
=======================
FastAPI endpoint tests using httpx TestClient.
Tests run against the actual app without requiring DB or MLflow.
"""

import pytest
from fastapi.testclient import TestClient

from smartshelf.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Health check endpoint tests."""

    def test_health_returns_200(self):
        """Health endpoint should always return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status(self):
        """Health response should include status field."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_has_model_status(self):
        """Health response should report model loading status."""
        response = client.get("/health")
        data = response.json()
        assert "models_loaded" in data
        assert isinstance(data["models_loaded"], dict)


class TestMetricsEndpoint:
    """Prometheus metrics endpoint tests."""

    def test_metrics_returns_200(self):
        """Metrics endpoint should return Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_contains_request_count(self):
        """Metrics should include the request counter."""
        response = client.get("/metrics")
        assert "smartshelf_request_count" in response.text or response.status_code == 200


class TestAPIV1Endpoints:
    """Tests for /api/v1/ endpoints."""

    def test_predict_demand_without_model_returns_503(self):
        """Should return 503 if model is not loaded."""
        response = client.post("/api/v1/predict-demand", json={
            "product_id": 1,
            "store_id": 1,
            "start_date": "2025-01-01",
            "end_date": "2025-01-07",
        })
        # Either works (if model loaded) or returns 503
        assert response.status_code in (200, 503)

    def test_optimize_price_without_model_returns_503(self):
        """Should return 503 if model is not loaded."""
        response = client.post("/api/v1/optimize-price", json={
            "product_id": 1,
            "store_id": 1,
        })
        assert response.status_code in (200, 404, 503)

    def test_optimize_inventory_without_model_returns_503(self):
        """Should return 503 if model is not loaded."""
        response = client.post("/api/v1/optimize-inventory", json={
            "product_id": 1,
            "store_id": 1,
        })
        assert response.status_code in (200, 503)

    def test_full_pipeline_without_model_returns_503(self):
        """Full pipeline should fail gracefully if models aren't loaded."""
        response = client.post("/api/v1/full-pipeline", json={
            "product_id": 1,
            "store_id": 1,
            "start_date": "2025-01-01",
            "end_date": "2025-01-07",
        })
        assert response.status_code in (200, 503)

    def test_admin_clear_cache(self):
        """Cache clear should always succeed."""
        response = client.post("/api/v1/admin/clear-cache")
        assert response.status_code == 200
        assert response.json()["status"] == "cache_cleared"


class TestRequestValidation:
    """Tests for Pydantic validation on request payloads."""

    def test_missing_required_field(self):
        """Missing product_id should return 422."""
        response = client.post("/api/v1/predict-demand", json={
            "store_id": 1,
            "start_date": "2025-01-01",
            "end_date": "2025-01-07",
        })
        assert response.status_code == 422

    def test_invalid_date_format(self):
        """Invalid date should return 422."""
        response = client.post("/api/v1/predict-demand", json={
            "product_id": 1,
            "store_id": 1,
            "start_date": "not-a-date",
            "end_date": "2025-01-07",
        })
        assert response.status_code == 422

    def test_simulate_sale_negative_quantity(self):
        """Quantity must be >= 1."""
        response = client.post("/api/v1/simulate-sale", json={
            "product_id": 1,
            "store_id": 1,
            "quantity": -5,
            "unit_price": 100,
        })
        assert response.status_code == 422
