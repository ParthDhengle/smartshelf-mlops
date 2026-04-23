import pandas as pd
from fastapi import APIRouter
from smartshelf.api.dependencies import get_db_engine
from smartshelf.api.schemas import InventoryTransactionCreate

router = APIRouter()

@router.get("/inventory")
async def get_inventory(limit: int = 100):
    engine = get_db_engine()
    df = pd.read_sql(f"SELECT * FROM inventory ORDER BY store_id, product_id LIMIT {limit}", engine)
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
