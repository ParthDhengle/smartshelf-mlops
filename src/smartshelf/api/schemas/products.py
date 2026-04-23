"""
SmartShelf — Pydantic Schemas (Products & Categories)
"""
from typing import Optional
from pydantic import BaseModel

class CategorySummary(BaseModel):
    category_id: int
    category_name: str
    parent_category_id: Optional[int] = None

class ProductSummary(BaseModel):
    product_id: int
    product_name: str
    category: str
    brand: str
    base_price: float
    cost_price: float
    perishable: bool
    avg_daily_demand: Optional[float] = None

class ProductCreate(BaseModel):
    category_id: int
    product_name: str
    brand: str
    unit_size: str
    perishable: bool = False
    shelf_life_days: int = 0
    base_cost_price: float
    base_sell_price: float
    gross_margin: float

class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    unit_size: Optional[str] = None
    perishable: Optional[bool] = None
    shelf_life_days: Optional[int] = None
    base_cost_price: Optional[float] = None
    base_sell_price: Optional[float] = None
    gross_margin: Optional[float] = None
