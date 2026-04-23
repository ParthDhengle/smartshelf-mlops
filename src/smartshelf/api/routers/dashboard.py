import logging
from datetime import datetime

import mlflow
import logging
from datetime import datetime

import mlflow
import pandas as pd
from fastapi import APIRouter

from smartshelf.monitoring.drift_detector import run_drift_detection
from smartshelf.api.dependencies import get_db_engine, clear_model_cache
from smartshelf.api.schemas import KPIResponse, StoreSummary
from smartshelf.config import (
    MLFLOW_TRACKING_URI,
    MODEL_NAME_DEMAND,
    MODEL_NAME_PRICE,
    MODEL_NAME_INVENTORY,
)

logger = logging.getLogger(__name__)
from smartshelf.config import (
    MLFLOW_TRACKING_URI,
    MODEL_NAME_DEMAND,
    MODEL_NAME_PRICE,
    MODEL_NAME_INVENTORY,
)

logger = logging.getLogger(__name__)
router = APIRouter()



@router.get("/stores", response_model=list[StoreSummary])
async def list_stores():
    engine = get_db_engine()
    df = pd.read_sql("SELECT * FROM stores ORDER BY store_id", engine)
    return df.to_dict(orient="records")


@router.post("/admin/refresh-models")
async def refresh_models():
    clear_model_cache()
    return {"status": "success", "message": "Model cache cleared — models will be reloaded on next request"}

@router.get("/admin/drift-check")
async def run_drift_check():
    try:
        report = run_drift_detection()
        return {"status": "success", "report": report}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/dashboard/kpis", response_model=KPIResponse)
async def get_kpis():
    engine = get_db_engine()
    metrics = {
        "total_revenue": 0.0, "total_profit": 0.0, "avg_margin_pct": 0.0,
        "total_products": 0, "total_stores": 0, "stockout_rate": 0.0,
        "avg_demand": 0.0, "active_promos": 0,
        "avg_demand": 0.0, "active_promos": 0,
    }
    try:
        rev_prof = pd.read_sql("""
            SELECT SUM(line_total) as rev,
                   SUM((soi.unit_price - COALESCE(p.base_cost_price, soi.unit_price*0.7)) * soi.quantity) as prof
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


# ─── Dashboard Charts (LIVE from DB) ─────────────────────────────────────────
@router.get("/dashboard/sales-trend")
async def get_sales_trend():
    """Return daily revenue/profit for the last 30 days from real sales data."""
    engine = get_db_engine()
    try:
        df = pd.read_sql("""
            SELECT so.order_date::date as date,
                   SUM(soi.line_total) as revenue,
                   SUM((soi.unit_price - COALESCE(p.base_cost_price, soi.unit_price*0.7)) * soi.quantity) as profit,
                   SUM(soi.quantity) as demand
            FROM sales_orders so
            JOIN sales_order_items soi ON so.order_id = soi.order_id
            JOIN products p ON soi.product_id = p.product_id
            GROUP BY so.order_date::date
            ORDER BY date DESC
            LIMIT 30
        """, engine)
        df = df.sort_values("date")
        df["date"] = df["date"].astype(str)
        import numpy as np
        df = df.replace({np.nan: 0})
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Sales trend query failed: {e}")
        return []


@router.get("/dashboard/category-breakdown")
async def get_category_breakdown():
    """Return revenue share per category (or brand if categories empty) from real DB data."""
    engine = get_db_engine()
    try:
        # Try category-based first (LEFT JOIN to handle empty categories table)
        df = pd.read_sql("""
            SELECT COALESCE(c.category_name, 'Category ' || p.category_id::text) as name,
                   SUM(soi.line_total) as value
            FROM sales_order_items soi
            JOIN products p ON soi.product_id = p.product_id
            LEFT JOIN categories c ON p.category_id = c.category_id
            GROUP BY COALESCE(c.category_name, 'Category ' || p.category_id::text)
            ORDER BY value DESC
            LIMIT 8
        """, engine)
        colors = ["#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]
        result = []
        total = float(df["value"].sum())
        for i, row in df.iterrows():
            result.append({
                "name": row["name"],
                "value": round(float(row["value"] / total * 100), 1) if total > 0 else 0,
                "color": colors[int(i) % len(colors)],
            })
        return result
    except Exception as e:
        logger.error(f"Category breakdown query failed: {e}")
        return []


# ─── MLflow Model Registry (LIVE) ────────────────────────────────────────────
@router.get("/admin/model-registry")
async def get_model_registry():
    """Pull model versions, stages, metrics and training dates dynamically from MLflow."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.MlflowClient()
    result = []

    for model_name in [MODEL_NAME_DEMAND, MODEL_NAME_PRICE, MODEL_NAME_INVENTORY]:
        try:
            versions = client.search_model_versions(f"name='{model_name}'")
            if not versions:
                result.append({
                    "name": model_name, "version": "—", "stage": "Not Registered",
                    "rmse": None, "last_trained": "—",
                })
                continue

            latest = max(versions, key=lambda v: int(v.version))

            # Determine stage: check aliases first, then legacy stage field
            stage = "None"
            try:
                rm = client.get_registered_model(model_name)
                if hasattr(rm, "aliases") and rm.aliases:
                    for alias_name, alias_version in rm.aliases.items():
                        if str(alias_version) == str(latest.version):
                            stage = alias_name.capitalize()
                            break
                if stage == "None" and hasattr(latest, "current_stage") and latest.current_stage:
                    stage = latest.current_stage
            except Exception:
                if hasattr(latest, "current_stage") and latest.current_stage:
                    stage = latest.current_stage

            # Pull run metrics for RMSE
            rmse = None
            last_trained = "—"
            try:
                run = client.get_run(latest.run_id)
                rmse = run.data.metrics.get("rmse") or run.data.metrics.get("test_rmse")
                if rmse is not None:
                    rmse = round(rmse, 2)
                # Training date from the run
                last_trained = datetime.fromtimestamp(run.info.start_time / 1000).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

            result.append({
                "name": model_name,
                "version": str(latest.version),
                "stage": stage,
                "rmse": rmse,
                "last_trained": last_trained,
            })
        except Exception as e:
            logger.error(f"Error fetching {model_name}: {e}")
            result.append({
                "name": model_name, "version": "—", "stage": "Error",
                "rmse": None, "last_trained": "—",
            })

    return result


@router.post("/admin/clear-cache")
async def admin_clear_cache():
    clear_model_cache()
    return {"status": "ok", "message": "Model cache cleared."}

# ─── Dashboard Charts (LIVE from DB) ─────────────────────────────────────────
@router.get("/dashboard/sales-trend")
async def get_sales_trend():
    """Return daily revenue/profit for the last 30 days from real sales data."""
    engine = get_db_engine()
    try:
        df = pd.read_sql("""
            SELECT so.order_date::date as date,
                   SUM(soi.line_total) as revenue,
                   SUM((soi.unit_price - COALESCE(p.base_cost_price, soi.unit_price*0.7)) * soi.quantity) as profit,
                   SUM(soi.quantity) as demand
            FROM sales_orders so
            JOIN sales_order_items soi ON so.order_id = soi.order_id
            JOIN products p ON soi.product_id = p.product_id
            GROUP BY so.order_date::date
            ORDER BY date DESC
            LIMIT 30
        """, engine)
        df = df.sort_values("date")
        df["date"] = df["date"].astype(str)
        import numpy as np
        df = df.replace({np.nan: 0})
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Sales trend query failed: {e}")
        return []


@router.get("/dashboard/category-breakdown")
async def get_category_breakdown():
    """Return revenue share per category (or brand if categories empty) from real DB data."""
    engine = get_db_engine()
    try:
        # Try category-based first (LEFT JOIN to handle empty categories table)
        df = pd.read_sql("""
            SELECT COALESCE(c.category_name, 'Category ' || p.category_id::text) as name,
                   SUM(soi.line_total) as value
            FROM sales_order_items soi
            JOIN products p ON soi.product_id = p.product_id
            LEFT JOIN categories c ON p.category_id = c.category_id
            GROUP BY COALESCE(c.category_name, 'Category ' || p.category_id::text)
            ORDER BY value DESC
            LIMIT 8
        """, engine)
        colors = ["#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]
        result = []
        total = float(df["value"].sum())
        for i, row in df.iterrows():
            result.append({
                "name": row["name"],
                "value": round(float(row["value"] / total * 100), 1) if total > 0 else 0,
                "color": colors[int(i) % len(colors)],
            })
        return result
    except Exception as e:
        logger.error(f"Category breakdown query failed: {e}")
        return []


# ─── MLflow Model Registry (LIVE) ────────────────────────────────────────────
@router.get("/admin/model-registry")
async def get_model_registry():
    """Pull model versions, stages, metrics and training dates dynamically from MLflow."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.MlflowClient()
    result = []

    for model_name in [MODEL_NAME_DEMAND, MODEL_NAME_PRICE, MODEL_NAME_INVENTORY]:
        try:
            versions = client.search_model_versions(f"name='{model_name}'")
            if not versions:
                result.append({
                    "name": model_name, "version": "—", "stage": "Not Registered",
                    "rmse": None, "last_trained": "—",
                })
                continue

            latest = max(versions, key=lambda v: int(v.version))

            # Determine stage: check aliases first, then legacy stage field
            stage = "None"
            try:
                rm = client.get_registered_model(model_name)
                if hasattr(rm, "aliases") and rm.aliases:
                    for alias_name, alias_version in rm.aliases.items():
                        if str(alias_version) == str(latest.version):
                            stage = alias_name.capitalize()
                            break
                if stage == "None" and hasattr(latest, "current_stage") and latest.current_stage:
                    stage = latest.current_stage
            except Exception:
                if hasattr(latest, "current_stage") and latest.current_stage:
                    stage = latest.current_stage

            # Pull run metrics for RMSE
            rmse = None
            last_trained = "—"
            try:
                run = client.get_run(latest.run_id)
                rmse = run.data.metrics.get("rmse") or run.data.metrics.get("test_rmse")
                if rmse is not None:
                    rmse = round(rmse, 2)
                # Training date from the run
                last_trained = datetime.fromtimestamp(run.info.start_time / 1000).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

            result.append({
                "name": model_name,
                "version": str(latest.version),
                "stage": stage,
                "rmse": rmse,
                "last_trained": last_trained,
            })
        except Exception as e:
            logger.error(f"Error fetching {model_name}: {e}")
            result.append({
                "name": model_name, "version": "—", "stage": "Error",
                "rmse": None, "last_trained": "—",
            })

    return result

