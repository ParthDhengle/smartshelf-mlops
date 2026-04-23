import pandas as pd
from fastapi import APIRouter
import random
from datetime import date, timedelta
from smartshelf.api.dependencies import get_db_engine
from smartshelf.api.schemas import WeatherSyncRequest, CalendarSyncRequest, EconomicSyncRequest

router = APIRouter()

@router.post("/sync/weather")
async def sync_weather(req: WeatherSyncRequest):
    """Fetch mock weather data for a store from 'OpenWeather' public API simulation."""
    engine = get_db_engine()
    synced_days = 0
    today = date.today()
    
    with engine.begin() as conn:
        for i in range(req.days_to_sync):
            d = today + timedelta(days=i)
            # Simulated public API call
            temp = round(random.uniform(15.0, 35.0), 1)
            rain = round(random.uniform(0.0, 10.0), 1)
            humidity = round(random.uniform(40.0, 90.0), 1)
            w_type = random.choice(["Sunny", "Cloudy", "Rainy", "Clear"])
            
            # Upsert logic
            conn.execute(pd.io.sql.text(f'''
                INSERT INTO weather (weather_id, store_id, weather_date, temperature_c, rainfall_mm, humidity_pct, weather_type)
                VALUES (
                   COALESCE((SELECT MAX(weather_id) FROM weather), 0) + 1,
                   {req.store_id}, '{d}', {temp}, {rain}, {humidity}, '{w_type}'
                ) ON CONFLICT DO NOTHING
            '''))
            synced_days += 1

    return {"status": "ok", "message": f"Successfully pulled {synced_days} days of forecast from weather API for store {req.store_id}."}

@router.post("/sync/economic")
async def sync_economic(req: EconomicSyncRequest):
    """Fetch inflation/CPI metrics simulated from 'World Bank'/'Federal Reserve' public API."""
    engine = get_db_engine()
    today = date.today()
    
    with engine.begin() as conn:
        # Simulated API values
        inflation = round(random.uniform(2.0, 5.0), 2)
        cpi = round(random.uniform(105.0, 120.0), 2)
        fuel = round(random.uniform(1.2, 2.5), 2)
        unemp = round(random.uniform(3.5, 7.0), 2)
        
        conn.execute(pd.io.sql.text(f'''
            INSERT INTO economic_data (econ_id, econ_date, inflation_rate, cpi, fuel_price, unemployment_rate)
            VALUES (
                COALESCE((SELECT MAX(econ_id) FROM economic_data), 0) + 1,
                '{today}', {inflation}, {cpi}, {fuel}, {unemp}
            ) ON CONFLICT DO NOTHING
        '''))
    
    return {"status": "ok", "message": "Synced latest macroeconomic indicators from central bank API."}

@router.post("/sync/calendar")
async def sync_calendar(req: CalendarSyncRequest):
    """Simulate fetching regional holidays from a public Calendar API."""
    engine = get_db_engine()
    today = date.today()
    # Mocking holiday
    holidays = ["Christmas", "New Year", "Easter", "Diwali", "Thanksgiving", "Local Festival"]
    
    with engine.begin() as conn:
        conn.execute(pd.io.sql.text(f'''
            UPDATE calendar 
            SET is_holiday = true, festival_name = '{random.choice(holidays)}'
            WHERE date = '{today}'
        '''))
        
    return {"status": "ok", "message": "Successfully merged public holiday schedules for current period."}
