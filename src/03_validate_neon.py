import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

conn_str = os.getenv("NEON_CONNECTION_STRING")
engine = create_engine(conn_str)

queries = {
    "total_linhas_fato": """
        SELECT COUNT(*) 
        FROM analytics.f_sales_order_line
    """,
    "total_vendas": """
        SELECT ROUND(SUM(sales_amount)::numeric, 2) 
        FROM analytics.f_sales_order_line
    """,
    "total_lucro": """
        SELECT ROUND(SUM(profit_amount)::numeric, 2) 
        FROM analytics.f_sales_order_line
    """,
    "total_quantidade": """
        SELECT SUM(quantity_sold) 
        FROM analytics.f_sales_order_line
    """,
    "total_pedidos_distintos": """
        SELECT COUNT(DISTINCT order_id_bk) 
        FROM analytics.f_sales_order_line
    """
}

with engine.connect() as conn:
    print("VALIDAÇÃO ANALÍTICA DA FATO\n")
    for nome, query in queries.items():
        result = conn.execute(text(query)).scalar()
        print(f"{nome}: {result}")