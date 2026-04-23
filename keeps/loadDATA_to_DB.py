import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

# Fix base path
BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), ".."))

LAYER1 = os.path.join(BASE_DIR, "data/raw/output_layer1")
LAYER2 = os.path.join(BASE_DIR, "data/raw/output_layer2")

# Check DB
with engine.connect() as conn:
    db = conn.execute(text("SELECT current_database();")).fetchone()
    print("✅ Connected to DB:", db[0])

tables = [
    "categories","stores","suppliers","products","product_suppliers",
    "product_costs","promotions","promotion_products","product_prices",
    "calendar","economic_data","sales_orders","sales_order_items",
    "weather","inventory","inventory_transactions",
    "purchase_orders","purchase_order_items",
]

for table in tables:
    path1 = os.path.join(LAYER1, f"{table}.csv")
    path2 = os.path.join(LAYER2, f"{table}.csv")

    path = path1 if os.path.exists(path1) else path2

    print(f"\n🔄 Loading {table}...")
    print("Path:", path)

    if not os.path.exists(path):
        print(f"❌ File not found for {table}")
        continue

    df = pd.read_csv(path)
    print(f"Rows: {len(df)}")

    df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=5000)

    print(f"✅ Done {table}")