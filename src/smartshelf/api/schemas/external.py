"""
SmartShelf — Pydantic Schemas (External Data Sync)
"""
from pydantic import BaseModel

class WeatherSyncRequest(BaseModel):
    store_id: int
    days_to_sync: int = 7

class EconomicSyncRequest(BaseModel):
    months_to_sync: int = 1

class CalendarSyncRequest(BaseModel):
    year: int
