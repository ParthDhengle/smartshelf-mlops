import pandas as pd
from fastapi import APIRouter, HTTPException
from datetime import datetime

from smartshelf.api.dependencies import get_db_engine
from smartshelf.api.schemas import SalesOrderCreate, SalesOrderItemCreate, SimulateSaleRequest

router = APIRouter()

@router.post("/simulate-sale")
async def simulate_sale(req: SimulateSaleRequest):
    """(Existing) Inject a simulated sale for testing."""
    engine = get_db_engine()
    
    max_order = pd.read_sql("SELECT COALESCE(MAX(order_id), 0) AS max_id FROM sales_orders", engine).iloc[0]["max_id"]
    new_order_id = int(max_order) + 1
    
    max_item = pd.read_sql("SELECT COALESCE(MAX(item_id), 0) AS max_id FROM sales_order_items", engine).iloc[0]["max_id"]
    new_item_id = int(max_item) + 1
    
    line_total = req.quantity * req.unit_price * (1 - req.discount_pct / 100)
    today = datetime.now().date()
    
    with engine.begin() as conn:
        conn.execute(pd.io.sql.text(f'''
            INSERT INTO sales_orders (order_id, store_id, order_date, total_amount, payment_method, customer_count)
            VALUES ({new_order_id}, {req.store_id}, '{today}', {line_total}, 'CREDIT', 1)
        '''))
        conn.execute(pd.io.sql.text(f'''
            INSERT INTO sales_order_items (item_id, order_id, product_id, quantity, unit_price, discount_pct, line_total)
            VALUES ({new_item_id}, {new_order_id}, {req.product_id}, {req.quantity}, {req.unit_price}, {req.discount_pct}, {line_total})
        '''))
        
        # Deduct inventory
        conn.execute(pd.io.sql.text(f'''
            UPDATE inventory 
            SET stock_on_hand = stock_on_hand - {req.quantity}, last_updated = CURRENT_TIMESTAMP
            WHERE store_id = {req.store_id} AND product_id = {req.product_id}
        '''))

    return {"status": "ok", "order_id": new_order_id, "amount_recorded": round(line_total, 2)}

@router.get("/sales")
async def list_recent_sales(limit: int = 50):
    engine = get_db_engine()
    df = pd.read_sql(f"SELECT * FROM sales_orders ORDER BY order_date DESC LIMIT {limit}", engine)
    return df.to_dict(orient="records")
