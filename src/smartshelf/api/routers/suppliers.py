import pandas as pd
from fastapi import APIRouter
from smartshelf.api.dependencies import get_db_engine

router = APIRouter()

@router.get("/suppliers")
async def list_suppliers():
    engine = get_db_engine()
    df = pd.read_sql("SELECT * FROM suppliers ORDER BY supplier_id", engine)
    return df.to_dict(orient="records")

@router.get("/purchase-orders")
async def list_purchase_orders(limit: int = 50):
    engine = get_db_engine()
    df = pd.read_sql(f"SELECT * FROM purchase_orders ORDER BY order_date DESC LIMIT {limit}", engine)
    return df.to_dict(orient="records")
