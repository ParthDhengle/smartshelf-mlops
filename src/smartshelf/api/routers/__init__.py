from fastapi import APIRouter
from . import ml_predictions, products, sales, inventory, suppliers, dashboard, external_data, store_optimization

api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["Dashboard"])
api_router.include_router(ml_predictions.router, tags=["ML Pipelines"])
api_router.include_router(products.router, tags=["Products & Categories"])
api_router.include_router(sales.router, tags=["Sales & Transactions"])
api_router.include_router(inventory.router, tags=["Inventory"])
api_router.include_router(suppliers.router, tags=["Suppliers"])
api_router.include_router(external_data.router, tags=["External Sync"])
api_router.include_router(store_optimization.router, tags=["Store Pricing Optimization"])
