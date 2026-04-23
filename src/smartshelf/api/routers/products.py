import pandas as pd
from fastapi import APIRouter, HTTPException

from smartshelf.api.dependencies import get_db_engine
from smartshelf.api.schemas import CategorySummary, ProductSummary, ProductCreate, ProductUpdate

router = APIRouter()

@router.get("/categories", response_model=list[CategorySummary])
async def list_categories():
    engine = get_db_engine()
    df = pd.read_sql("SELECT * FROM categories ORDER BY category_id", engine)
    return df.to_dict(orient="records")

@router.get("/products", response_model=list[ProductSummary])
async def list_products():
    engine = get_db_engine()
    df = pd.read_sql('''
        SELECT p.product_id, 
               COALESCE(p.product_name, 'Unknown') as product_name, 
               COALESCE(c.category_name, 'Uncategorized') as category, 
               COALESCE(p.brand, 'Unknown') as brand, 
               COALESCE(p.base_sell_price, 0.0) as base_price, 
               COALESCE(p.base_cost_price, 0.0) as cost_price, 
               COALESCE(p.perishable, false) as perishable 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.category_id
        ORDER BY p.product_id
    ''', engine)
    
    # Handle any remaining Pandas NaN values cleanly
    import numpy as np
    df = df.replace({np.nan: None})
    return df.to_dict(orient="records")

@router.post("/products", response_model=ProductSummary)
async def create_product(req: ProductCreate):
    engine = get_db_engine()
    max_id = pd.read_sql("SELECT COALESCE(MAX(product_id), 0) AS max_id FROM products", engine).iloc[0]["max_id"]
    new_id = int(max_id) + 1
    
    with engine.begin() as conn:
        conn.execute(pd.io.sql.text(f'''
            INSERT INTO products 
            (product_id, category_id, product_name, brand, unit_size, perishable, shelf_life_days, base_cost_price, base_sell_price, gross_margin, created_at)
            VALUES 
            ({new_id}, {req.category_id}, '{req.product_name}', '{req.brand}', '{req.unit_size}', {str(req.perishable).upper()}, {req.shelf_life_days}, {req.base_cost_price}, {req.base_sell_price}, {req.gross_margin}, CURRENT_TIMESTAMP)
        '''))
        
    df = pd.read_sql(f"SELECT p.product_id, p.product_name, c.category_name as category, p.brand, p.base_sell_price as base_price, p.base_cost_price as cost_price, p.perishable FROM products p LEFT JOIN categories c ON p.category_id = c.category_id WHERE p.product_id={new_id}", engine)
    return df.to_dict(orient="records")[0]

@router.put("/products/{product_id}")
async def update_product(product_id: int, req: ProductUpdate):
    engine = get_db_engine()
    set_clauses = []
    if req.category_id is not None: set_clauses.append(f"category_id={req.category_id}")
    if req.product_name is not None: set_clauses.append(f"product_name='{req.product_name}'")
    if req.brand is not None: set_clauses.append(f"brand='{req.brand}'")
    if req.unit_size is not None: set_clauses.append(f"unit_size='{req.unit_size}'")
    if req.perishable is not None: set_clauses.append(f"perishable={str(req.perishable).upper()}")
    if req.shelf_life_days is not None: set_clauses.append(f"shelf_life_days={req.shelf_life_days}")
    if req.base_cost_price is not None: set_clauses.append(f"base_cost_price={req.base_cost_price}")
    if req.base_sell_price is not None: set_clauses.append(f"base_sell_price={req.base_sell_price}")
    if req.gross_margin is not None: set_clauses.append(f"gross_margin={req.gross_margin}")
    
    if not set_clauses: return {"status": "ok", "message": "No fields to update"}
        
    with engine.begin() as conn:
        res = conn.execute(pd.io.sql.text(f"UPDATE products SET {', '.join(set_clauses)} WHERE product_id={product_id}"))
        if res.rowcount == 0: raise HTTPException(404, "Product not found")
            
    return {"status": "ok", "product_id": product_id}

@router.delete("/products/{product_id}")
async def delete_product(product_id: int):
    engine = get_db_engine()
    try:
        with engine.begin() as conn:
            res = conn.execute(pd.io.sql.text(f"DELETE FROM products WHERE product_id={product_id}"))
            if res.rowcount == 0: raise HTTPException(404, "Product not found")
        return {"status": "ok", "product_id": product_id}
    except Exception as e:
        if "foreign key constraint" in str(e).lower():
            raise HTTPException(400, "Cannot delete product because dependent records exist.")
        raise HTTPException(500, str(e))
