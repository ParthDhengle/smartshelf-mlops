import pandas as pd
from fastapi import APIRouter
from smartshelf.api.dependencies import get_db_engine
from smartshelf.api.schemas import InventoryTransactionCreate

router = APIRouter()

@router.get("/inventory")
async def get_inventory(store_id: int = 1, limit: int = 500):
    engine = get_db_engine()
    df = pd.read_sql(f"""
        SELECT i.*, 
               COALESCE(p.product_name, 'Unknown') as product_name,
               p.base_sell_price,
               p.base_cost_price,
               p.perishable,
               p.shelf_life_days
        FROM inventory i
        LEFT JOIN products p ON i.product_id = p.product_id
        WHERE i.store_id = {store_id}
        ORDER BY i.stock_on_hand ASC, i.product_id
        LIMIT {limit}
    """, engine)
    import numpy as np
    df = df.replace({np.nan: None})
    return df.to_dict(orient="records")

@router.post("/inventory/transaction")
async def create_inventory_transaction(req: InventoryTransactionCreate):
    engine = get_db_engine()
    try:
        with engine.begin() as conn:
            # Simple stock update
            sign = 1 if req.txn_type.lower() in ("receive", "return") else -1
            conn.execute(pd.io.sql.text(f'''
                UPDATE inventory 
                SET stock_on_hand = stock_on_hand + ({sign * req.quantity}), last_updated = CURRENT_TIMESTAMP
                WHERE store_id = {req.store_id} AND product_id = {req.product_id}
            '''))
        return {"status": "ok", "message": "Inventory updated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
