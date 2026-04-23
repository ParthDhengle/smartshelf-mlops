"""
SmartShelf — Pydantic Schemas (Dashboard & Health)
"""
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    mlflow_connected: bool
    db_connected: bool
    models_loaded: dict

class KPIResponse(BaseModel):
    total_revenue: float
    total_profit: float
    avg_margin_pct: float
    total_products: int
    total_stores: int
    stockout_rate: float
    avg_demand: float
    active_promos: int
