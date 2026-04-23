import pandas as pd
from fastapi import APIRouter
from smartshelf.api.dependencies import get_db_engine, clear_model_cache
from smartshelf.api.schemas import KPIResponse, StoreSummary

router = APIRouter()

@router.get("/stores", response_model=list[StoreSummary])
async def list_stores():
    engine = get_db_engine()
    df = pd.read_sql("SELECT * FROM stores ORDER BY store_id", engine)
    return df.to_dict(orient="records")

@router.get("/dashboard/kpis", response_model=KPIResponse)
async def get_kpis():
    engine = get_db_engine()
    metrics = {
        "total_revenue": 0.0, "total_profit": 0.0, "avg_margin_pct": 0.0,
        "total_products": 0, "total_stores": 0, "stockout_rate": 0.0,
        "avg_demand": 0.0, "active_promos": 0
    }
    try:
        rev_prof = pd.read_sql("""
            SELECT SUM(line_total) as rev, 
                   SUM((soi.unit_price - COALESCE(p.base_cost_price, soi.unit_price*0.7)) * soi.quantity) as prof 
            FROM sales_order_items soi
            JOIN products p ON soi.product_id = p.product_id
        """, engine)
        if not rev_prof.empty:
            metrics["total_revenue"] = float(rev_prof.iloc[0]["rev"] or 0)
            metrics["total_profit"] = float(rev_prof.iloc[0]["prof"] or 0)
            if metrics["total_revenue"] > 0:
                metrics["avg_margin_pct"] = round((metrics["total_profit"] / metrics["total_revenue"]) * 100, 1)

        counts = pd.read_sql("SELECT (SELECT COUNT(*) FROM products) as p_cnt, (SELECT COUNT(*) FROM stores) as s_cnt", engine)
        metrics["total_products"] = int(counts.iloc[0]["p_cnt"])
        metrics["total_stores"] = int(counts.iloc[0]["s_cnt"])

        so = pd.read_sql("SELECT COUNT(*) as st, (SELECT COUNT(*) FROM inventory) as tot FROM inventory WHERE stock_on_hand <= 0", engine)
        if int(so.iloc[0]["tot"]) > 0:
            metrics["stockout_rate"] = round((int(so.iloc[0]["st"]) / int(so.iloc[0]["tot"])) * 100, 1)

        dm = pd.read_sql("SELECT AVG(daily_units) as avg_d FROM (SELECT SUM(quantity) as daily_units FROM sales_order_items soi JOIN sales_orders so ON soi.order_id=so.order_id GROUP BY so.order_date, soi.product_id) sub", engine)
        metrics["avg_demand"] = round(float(dm.iloc[0]["avg_d"] or 0), 1)

        pr = pd.read_sql("SELECT COUNT(*) as act FROM promotions WHERE CURRENT_DATE BETWEEN start_date AND end_date", engine)
        metrics["active_promos"] = int(pr.iloc[0]["act"])
    except Exception:
        pass
    return KPIResponse(**metrics)

@router.post("/admin/clear-cache")
async def admin_clear_cache():
    clear_model_cache()
    return {"status": "ok", "message": "Model cache cleared."}
