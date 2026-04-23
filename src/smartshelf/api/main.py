"""
SmartShelf — FastAPI Application
=================================
Production-ready API server with:
  - CORS for frontend access
  - Prometheus metrics middleware
  - Health check endpoint
  - All ML prediction + data endpoints
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

from smartshelf.api.dependencies import (
    check_db_connection,
    check_mlflow_connection,
    get_loaded_models_status,
)
from smartshelf.api.routers import api_router
from smartshelf.api.schemas.dashboard import HealthResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═════════════════════════════════════════════════════════════════════════════

REQUEST_COUNT = Counter(
    "smartshelf_request_count",
    "Total API requests",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "smartshelf_request_latency_seconds",
    "API request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# ═════════════════════════════════════════════════════════════════════════════
# APP
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="SmartShelf API",
    description="Production-grade Retail AI — Demand Forecasting, Price Optimization, Inventory Management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend (Next.js dev server + production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE — Request metrics
# ═════════════════════════════════════════════════════════════════════════════

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request count and latency for Prometheus."""
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start

    endpoint = request.url.path
    method = request.method
    status = str(response.status_code)

    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)

    return response


# ═════════════════════════════════════════════════════════════════════════════
# CORE ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse)
async def health():
    """Comprehensive health check — DB, MLflow, model status."""
    db_ok = check_db_connection()
    mlflow_ok = check_mlflow_connection()
    models = get_loaded_models_status()

    status = "healthy" if (db_ok and mlflow_ok) else "degraded"

    return HealthResponse(
        status=status,
        mlflow_connected=mlflow_ok,
        db_connected=db_ok,
        models_loaded=models,
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint — scraped by Prometheus."""
    return Response(content=generate_latest(), media_type="text/plain")


# Include all route handlers
app.include_router(api_router, prefix="/api/v1")


# ═════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    from smartshelf.config import API_HOST, API_PORT

    uvicorn.run(
        "smartshelf.api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info",
    )
