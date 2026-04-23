"""
SmartShelf — Feature Sync Flow
==============================
Periodically syncs operational OLTP databases (PostgreSQL)
to analytical data warehouses (BigQuery).

Usage:
  python src/smartshelf/flows/feature_flow.py
"""

from prefect import task, flow
import logging

logger = logging.getLogger(__name__)

@task(name="Sync PostgreSQL -> BigQuery", retries=3, retry_delay_seconds=300)
def sync_to_data_warehouse_task():
    """Calls the pandas-gbq scripts pushing data into Google BigQuery."""
    from smartshelf.pipelines.postgres_to_bq import sync_tables_to_bq
    try:
        # Utilizing the highly optimized existing DWH ingestion pipeline!
        sync_tables_to_bq()
    except Exception as e:
        logger.error(f"BigQuery Sync Failed: {e}")
        raise e

@flow(name="Daily Data Warehouse Sync")
def daily_feature_sync_flow():
    logger.info("Starting Daily DB->BigQuery Sync flow...")
    sync_to_data_warehouse_task()

if __name__ == "__main__":
    daily_feature_sync_flow()
