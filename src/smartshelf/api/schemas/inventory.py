"""
SmartShelf — Pydantic Schemas (Inventory)
"""
from pydantic import BaseModel
from typing import Optional
from datetime import date

class InventoryTransactionCreate(BaseModel):
    product_id: int
    store_id: int
    txn_type: str
    quantity: int
    notes: Optional[str] = None
