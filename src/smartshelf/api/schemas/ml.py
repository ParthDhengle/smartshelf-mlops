"""
SmartShelf — Pydantic Schemas (Machine Learning)
"""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field

class DemandRequest(BaseModel):
    product_id: int
    store_id: int
    start_date: date
    end_date: date

class DemandPrediction(BaseModel):
    date: date
    predicted_demand: float
    confidence_lower: Optional[float] = None
    confidence_upper: Optional[float] = None

class DemandResponse(BaseModel):
    product_id: int
    store_id: int
    forecasts: List[DemandPrediction]
    total_predicted: float
    model_version: Optional[str] = None

class PriceRequest(BaseModel):
    product_id: int
    store_id: int
    current_price: Optional[float] = None
    cost_price: Optional[float] = None
    predicted_demand: Optional[float] = None

class PriceResponse(BaseModel):
    product_id: int
    store_id: int
    current_price: float
    optimal_price: float
    expected_demand: float
    expected_profit: float
    price_elasticity: Optional[float] = None
    profit_uplift_pct: Optional[float] = None

class InventoryRequest(BaseModel):
    product_id: int
    store_id: int
    predicted_demand: Optional[float] = None
    optimal_price: Optional[float] = None

class InventoryResponse(BaseModel):
    product_id: int
    store_id: int
    reorder_point: int
    safety_stock: int
    order_qty: int
    predicted_daily_demand: float
    days_of_stock_left: Optional[float] = None
    current_stock: Optional[int] = None

class FullPipelineRequest(BaseModel):
    product_id: int
    store_id: int
    start_date: date
    end_date: date

class FullPipelineResponse(BaseModel):
    product_id: int
    store_id: int
    demand: DemandResponse
    price: PriceResponse
    inventory: InventoryResponse
    total_expected_profit: float
