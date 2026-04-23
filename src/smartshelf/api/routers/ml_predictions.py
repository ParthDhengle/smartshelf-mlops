import logging
from datetime import date, timedelta
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from smartshelf.api.dependencies import (
    get_demand_model, get_price_model, get_inventory_model, 
    get_product_info, get_db_engine, get_current_inventory
)
from smartshelf.api.schemas import (
    DemandRequest, DemandResponse, DemandPrediction,
    PriceRequest, PriceResponse, 
    InventoryRequest, InventoryResponse,
    FullPipelineRequest, FullPipelineResponse
)
# Reusing the feature building function from the old routes.py 
# We'll just define it or import. Here we move the function logic locally:

def build_inference_features(product_id: int, store_id: int, target_date: date) -> pd.DataFrame:
    engine = get_db_engine()

    # Recent sales for lag/rolling features
    sales = pd.read_sql(f"""
        SELECT
            so.order_date::date AS date,
            SUM(soi.quantity)   AS units_sold
        FROM sales_order_items soi
        JOIN sales_orders so ON soi.order_id = so.order_id
        WHERE soi.product_id = {product_id}
          AND so.store_id = {store_id}
          AND so.order_date >= '{target_date - timedelta(days=35)}'::date
          AND so.order_date < '{target_date}'::date
        GROUP BY so.order_date::date
        ORDER BY so.order_date::date
    """, engine)

    sales["date"] = pd.to_datetime(sales["date"])
    sales = sales.set_index("date").reindex(
        pd.date_range(target_date - timedelta(days=35), target_date - timedelta(days=1)),
        fill_value=0
    ).reset_index().rename(columns={"index": "date"})

    units = sales["units_sold"].values

    row = {
        "units_sold_lag_7": units[-7] if len(units) >= 7 else 0,
        "units_sold_lag_14": units[-14] if len(units) >= 14 else 0,
        "units_sold_lag_28": units[-28] if len(units) >= 28 else 0,
    }

    for window in [7, 14, 28]:
        if len(units) >= window:
            window_data = units[-window:]
            row[f"units_sold_roll_mean_{window}"] = float(np.mean(window_data))
            row[f"units_sold_roll_std_{window}"] = float(np.std(window_data))
        else:
            row[f"units_sold_roll_mean_{window}"] = float(np.mean(units)) if len(units) > 0 else 0
            row[f"units_sold_roll_std_{window}"] = 0

    price_row = pd.read_sql(f"""
        SELECT selling_price, competitor_price, discount_pct
        FROM product_prices
        WHERE product_id = {product_id} AND store_id = {store_id}
          AND effective_date <= '{target_date}'
        ORDER BY effective_date DESC LIMIT 1
    """, engine)

    if not price_row.empty:
        pr = price_row.iloc[0]
        row["selling_price"] = float(pr["selling_price"])
        row["competitor_price"] = float(pr["competitor_price"] or pr["selling_price"])
        row["discount_pct"] = float(pr["discount_pct"] or 0)
    else:
        row["selling_price"] = 0
        row["competitor_price"] = 0
        row["discount_pct"] = 0

    row["effective_price"] = row["selling_price"] * (1 - row["discount_pct"] / 100)
    row["price_vs_competitor"] = row["selling_price"] - row["competitor_price"]
    row["price_discount_interaction"] = row["selling_price"] * row["discount_pct"] / 100

    product = get_product_info(product_id)
    if product:
        row["perishable"] = int(product.get("perishable", False))
        row["shelf_life_days"] = int(product.get("shelf_life_days", 0))
        row["margin_pct"] = float(product.get("gross_margin", 0))
        row["cost_price"] = float(product.get("base_cost_price", 0))
        row["base_sell_price"] = float(product.get("base_sell_price", 0))
        row["gross_margin"] = float(product.get("gross_margin", 0))
    else:
        row.update({"perishable": 0, "shelf_life_days": 0, "margin_pct": 0,
                     "cost_price": 0, "base_sell_price": 0, "gross_margin": 0})

    store = pd.read_sql(f"SELECT store_type, store_size_sqft FROM stores WHERE store_id = {store_id}", engine)
    if not store.empty:
        row["store_size_sqft"] = float(store.iloc[0]["store_size_sqft"])
        row["store_type_encoded"] = hash(store.iloc[0]["store_type"]) % 10
    else:
        row["store_size_sqft"] = 0
        row["store_type_encoded"] = 0

    target_dt = pd.Timestamp(target_date)
    row["day_of_week"] = target_dt.dayofweek
    row["month"] = target_dt.month
    row["quarter"] = target_dt.quarter
    row["is_weekend"] = int(target_dt.dayofweek >= 5)

    cal = pd.read_sql(f"SELECT is_holiday, season FROM calendar WHERE date = '{target_date}'", engine)
    if not cal.empty:
        row["is_holiday"] = int(cal.iloc[0]["is_holiday"])
        row["season_encoded"] = hash(cal.iloc[0]["season"]) % 5
    else:
        row["is_holiday"] = 0
        row["season_encoded"] = 0

    weather = pd.read_sql(f"""
        SELECT temperature_c, rainfall_mm, humidity_pct, weather_type
        FROM weather
        WHERE store_id = {store_id} AND weather_date = '{target_date}'
    """, engine)
    if not weather.empty:
        w = weather.iloc[0]
        row["temperature_c"] = float(w["temperature_c"] or 25)
        row["rainfall_mm"] = float(w["rainfall_mm"] or 0)
        row["humidity_pct"] = float(w["humidity_pct"] or 50)
        row["weather_type_encoded"] = hash(w["weather_type"]) % 5
    else:
        row.update({"temperature_c": 25, "rainfall_mm": 0, "humidity_pct": 50, "weather_type_encoded": 0})

    econ = pd.read_sql(f"""
        SELECT inflation_rate, cpi, fuel_price, unemployment_rate
        FROM economic_data
        WHERE econ_date <= '{target_date}'
        ORDER BY econ_date DESC LIMIT 1
    """, engine)
    if not econ.empty:
        e = econ.iloc[0]
        row["inflation_rate"] = float(e["inflation_rate"] or 0)
        row["cpi"] = float(e["cpi"] or 0)
        row["fuel_price"] = float(e["fuel_price"] or 0)
        row["unemployment_rate"] = float(e["unemployment_rate"] or 0)
    else:
        row.update({"inflation_rate": 0, "cpi": 0, "fuel_price": 0, "unemployment_rate": 0})

    if product:
        row["category_encoded"] = hash(product.get("category_name", "")) % 20
    else:
        row["category_encoded"] = 0

    return pd.DataFrame([row])


router = APIRouter()

@router.post("/predict-demand", response_model=DemandResponse)
async def predict_demand(req: DemandRequest):
    model = get_demand_model()
    if model is None:
        raise HTTPException(503, "Demand model not available.")

    forecasts = []
    total = 0.0
    current = req.start_date
    while current <= req.end_date:
        features = build_inference_features(req.product_id, req.store_id, current)
        pred = float(max(model.predict(features)[0], 0))
        total += pred
        forecasts.append(DemandPrediction(
            date=current,
            predicted_demand=round(pred, 2),
            confidence_lower=round(pred * 0.8, 2),
            confidence_upper=round(pred * 1.2, 2),
        ))
        current += timedelta(days=1)

    return DemandResponse(product_id=req.product_id, store_id=req.store_id, forecasts=forecasts, total_predicted=round(total, 2))


@router.post("/optimize-price", response_model=PriceResponse)
async def optimize_price(req: PriceRequest):
    model = get_price_model()
    if model is None:
        raise HTTPException(503, "Price model not available.")

    product = get_product_info(req.product_id)
    if not product: raise HTTPException(404, "Product not found")

    cost = req.cost_price or float(product.get("base_cost_price", 0))
    current_price = req.current_price or float(product.get("base_sell_price", 0))

    features = build_inference_features(req.product_id, req.store_id, date.today())
    if req.predicted_demand is not None: features["predicted_demand"] = req.predicted_demand
    features["cost_price"] = cost
    features["base_sell_price"] = current_price
    features["gross_margin"] = float(product.get("gross_margin", 0))

    best_profit = -np.inf
    best_price = current_price
    best_demand = 0

    for price in np.linspace(max(cost * 0.8, 1.0), current_price * 2.5, 30):
        f = features.copy()
        f["selling_price"] = price
        f["effective_price"] = price * (1 - f["discount_pct"].iloc[0] / 100)
        f["price_vs_competitor"] = price - f["competitor_price"].iloc[0]
        demand = max(float(model.predict(f)[0]), 0)
        profit = (price - cost) * demand
        if profit > best_profit:
            best_profit, best_price, best_demand = profit, price, demand

    p_curr = (current_price - cost) * max(float(model.predict(features)[0]), 0)
    uplift = ((best_profit - p_curr) / (p_curr + 1e-8)) * 100

    return PriceResponse(product_id=req.product_id, store_id=req.store_id, current_price=round(current_price, 2), optimal_price=round(best_price, 2), expected_demand=round(best_demand, 2), expected_profit=round(best_profit, 2), profit_uplift_pct=round(uplift, 1))

@router.post("/optimize-inventory", response_model=InventoryResponse)
async def optimize_inventory(req: InventoryRequest):
    model = get_inventory_model()
    if model is None: raise HTTPException(503, "Inventory model not available.")

    features = build_inference_features(req.product_id, req.store_id, date.today())
    if req.predicted_demand is not None: features["predicted_demand"] = req.predicted_demand
    if req.optimal_price is not None: features["optimal_price"] = req.optimal_price

    engine = get_db_engine()
    supplier = pd.read_sql(f"SELECT s.lead_time_days, s.delivery_cost, s.reliability_score FROM product_suppliers ps JOIN suppliers s ON ps.supplier_id = s.supplier_id WHERE ps.product_id = {req.product_id} ORDER BY s.delivery_cost ASC LIMIT 1", engine)

    if not supplier.empty:
        features["lead_time_days"] = float(supplier.iloc[0]["lead_time_days"])
        features["delivery_cost"] = float(supplier.iloc[0]["delivery_cost"])
        features["reliability_score"] = float(supplier.iloc[0]["reliability_score"])
    else:
        features.update({"lead_time_days": 3, "delivery_cost": 50, "reliability_score": 0.9})

    features["demand_std"] = features.get("units_sold_roll_std_28", pd.Series([0]))[0]
    features["lead_time_variance"] = 0

    safety = max(int(model.predict(features)[0]), 0)
    lt = features["lead_time_days"].iloc[0]
    daily_d = features.get("predicted_demand", pd.Series([0])).iloc[0]
    reorder = int(daily_d * lt + safety)

    holding = features["cost_price"].iloc[0] * 0.25 + 0.01
    annual = daily_d * 365
    eoq = int(np.sqrt(2 * annual * features["delivery_cost"].iloc[0] / holding)) if annual > 0 else 0

    inv = get_current_inventory(req.product_id, req.store_id)
    current_stock = inv["stock_on_hand"] if inv else None
    dos = round(current_stock / (daily_d + 0.01), 1) if current_stock else None

    return InventoryResponse(product_id=req.product_id, store_id=req.store_id, reorder_point=reorder, safety_stock=safety, order_qty=eoq, predicted_daily_demand=round(daily_d, 2), current_stock=current_stock, days_of_stock_left=dos)

@router.post("/full-pipeline", response_model=FullPipelineResponse)
async def full_pipeline(req: FullPipelineRequest):
    demand = await predict_demand(DemandRequest(product_id=req.product_id, store_id=req.store_id, start_date=req.start_date, end_date=req.end_date))
    avg_demand = demand.total_predicted / max(len(demand.forecasts), 1)
    price = await optimize_price(PriceRequest(product_id=req.product_id, store_id=req.store_id, predicted_demand=avg_demand))
    inv = await optimize_inventory(InventoryRequest(product_id=req.product_id, store_id=req.store_id, predicted_demand=avg_demand, optimal_price=price.optimal_price))
    return FullPipelineResponse(product_id=req.product_id, store_id=req.store_id, demand=demand, price=price, inventory=inv, total_expected_profit=price.expected_profit)
