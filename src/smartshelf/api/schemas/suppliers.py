"""
SmartShelf — Pydantic Schemas (Suppliers)
"""
from pydantic import BaseModel
from datetime import date
from typing import Optional

class SupplierSummary(BaseModel):
    supplier_id: int
    supplier_name: str
    city: str
    lead_time_days: int
    delivery_cost: float
    reliability_score: float

class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    store_id: int
    expected_delivery: date
    status: str
    total_cost: float
