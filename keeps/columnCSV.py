import pandas as pd
import os
import json

csv_files = [
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/calendar.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/economic_data.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/product_costs.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/product_prices.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/product_suppliers.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/products.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/promotion_products.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/promotions.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/stores.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer1/suppliers.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/inventory_transactions.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/inventory.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/purchase_order_items.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/purchase_orders.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/sales_order_items.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/sales_orders.csv",
    "C:/Users/parth/Desktop/Projects/MLOPS/smartshelf-mlops/data/raw/output_layer2/weather.csv"
]

def extract_columns(file_paths):
    file_columns_map = {}

    for file_path in file_paths:
        try:
            file_name = os.path.basename(file_path)
            df = pd.read_csv(file_path, nrows=0)

            file_columns_map[file_name] = {
                "num_columns": len(df.columns),
                "columns": df.columns.tolist()
            }

        except Exception as e:
            file_columns_map[file_path] = {"error": str(e)}

    return file_columns_map


if __name__ == "__main__":
    result = extract_columns(csv_files)

    # Save to JSON (useful for schema tracking)
    with open("schema.json", "w") as f:
        json.dump(result, f, indent=4)

    print("✅ Schema saved to schema.json")