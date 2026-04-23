import logging
import pandas as pd
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException

from smartshelf.api.schemas import (
    StoreOptimizationRequest, StoreOptimizationItem, StoreOptimizationResponse,
    DemandRequest, PriceRequest
)
from smartshelf.api.dependencies import get_db_engine
from smartshelf.api.routers.ml_predictions import predict_demand, optimize_price

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/optimize-store", response_model=StoreOptimizationResponse)
async def optimize_store(req: StoreOptimizationRequest):
    """
    Execute a mass batch-prediction of demand and price across all active
    inventory products for a specific store to generate an entire 7-day 
    pricing directive.
    """
    engine = get_db_engine()
    
    # 1. Fetch products active in this store
    # Limit to 30 for demo speed so the endpoint doesn't hang taking 5 mins
    query = f"""
        SELECT p.product_id, p.product_name 
        FROM products p
        JOIN inventory i ON p.product_id = i.product_id
        WHERE i.store_id = {req.store_id}
        LIMIT 30
    """
    try:
        products_df = pd.read_sql(query, engine)
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")
        
    if products_df.empty:
        raise HTTPException(404, "No products found in inventory for this store.")

    optimizations = []
    total_expected_profit = 0.0
    
    start_date = date.today()
    end_date = start_date + timedelta(days=6)
    
    # 2. Loop over products and run pipeline natively
    for _, row in products_df.iterrows():
        p_id = int(row["product_id"])
        name = str(row["product_name"])
        
        try:
            # Predict Demand for next 7 days
            d_req = DemandRequest(product_id=p_id, store_id=req.store_id, start_date=start_date, end_date=end_date)
            demand_resp = await predict_demand(d_req)
            
            avg_daily_demand = demand_resp.total_predicted / max(len(demand_resp.forecasts), 1)
            
            # Predict Optimal Price
            p_req = PriceRequest(product_id=p_id, store_id=req.store_id, predicted_demand=avg_daily_demand)
            price_resp = await optimize_price(p_req)
            
            # Convert daily profit to 7-day profit window
            profit_7d = price_resp.expected_profit * 7
            
            opt = StoreOptimizationItem(
                product_id=p_id,
                product_name=name,
                current_price=price_resp.current_price,
                optimal_price=price_resp.optimal_price,
                expected_7d_demand=round(demand_resp.total_predicted, 2),
                expected_7d_profit=round(profit_7d, 2),
                profit_uplift_pct=price_resp.profit_uplift_pct
            )
            optimizations.append(opt)
            total_expected_profit += profit_7d
            
        except Exception as e:
            logger.warning(f"Failed to optimize product {p_id}: {e}")
            continue

    if not optimizations:
        raise HTTPException(500, "Models failed to generate predictions for store products. Check Model availability.")

    # Sort by absolute profit magnitude to show most important items first
    optimizations.sort(key=lambda x: x.expected_7d_profit, reverse=True)

    return StoreOptimizationResponse(
        store_id=req.store_id,
        total_expected_profit=round(total_expected_profit, 2),
        optimizations=optimizations
    )
