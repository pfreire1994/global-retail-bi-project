import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(r"C:\Users\paulafreire\Documents\tcc_analytics_bi")
CURATED_DIR = BASE_DIR / "data" / "curated"

conn_str = os.getenv("NEON_CONNECTION_STRING")
engine = create_engine(conn_str)

tables_in_order = [
    "d_calendar",
    "d_customer",
    "d_product",
    "d_geography",
    "d_market",
    "d_ship_mode",
    "d_order_priority",
    "d_discount_band",
    "d_profitability_band",
    "f_sales_order_line",
]

print("Garantindo schema analytics...")
with engine.connect() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
    conn.commit()

for table_name in tables_in_order:
    file_path = CURATED_DIR / f"{table_name}.csv"

    print(f"\nLendo {table_name}...")
    df = pd.read_csv(file_path)
    print(f"Linhas: {len(df)}")

    print(f"Carregando analytics.{table_name} ...")
    df.to_sql(
        name=table_name,
        con=engine,
        schema="analytics",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000
    )

    print(f"analytics.{table_name} carregada com sucesso.")

print("\nCarga completa finalizada com sucesso.")