"""
SmartShelf — Pydantic Schemas (Stores)
"""
from pydantic import BaseModel

class StoreSummary(BaseModel):
    store_id: int
    store_name: str
    city: str
    state: str
    store_type: str
    store_size_sqft: float
