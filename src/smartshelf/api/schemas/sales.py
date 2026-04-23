"""
SmartShelf — Pydantic Schemas (Sales)
"""
from typing import Optional
from datetime import date
from pydantic import BaseModel, Field

class SimulateSaleRequest(BaseModel):
    product_id: int
    store_id: int
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., gt=0)
    discount_pct: float = Field(0.0, ge=0, le=100)

class SalesOrderCreate(BaseModel):
    store_id: int
    order_date: date
    total_amount: float
    payment_method: str
    customer_count: int

class SalesOrderItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: float
    discount_pct: float
    line_total: float
