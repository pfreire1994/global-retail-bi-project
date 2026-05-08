import re
import unicodedata
from pathlib import Path

import pandas as pd


# ============================================
# CONFIGURAÇÃO DE PASTAS
# ============================================
BASE_DIR = Path(r"C:\Users\paulafreire\Documents\tcc_analytics_bi")
RAW_FILE = BASE_DIR / "data" / "raw" / "superstore.csv"
STAGING_DIR = BASE_DIR / "data" / "staging"
CURATED_DIR = BASE_DIR / "data" / "curated"
LOGS_DIR = BASE_DIR / "logs"

STAGING_DIR.mkdir(parents=True, exist_ok=True)
CURATED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================
# FUNÇÕES AUXILIARES
# ============================================
def normalize_column_name(col: str) -> str:
    col = str(col).strip().lower()
    col = col.replace(".", "_").replace(" ", "_").replace("-", "_").replace("/", "_")
    col = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode("utf-8")
    col = re.sub(r"[^a-z0-9_]", "", col)
    col = re.sub(r"_+", "_", col).strip("_")
    return col


def add_surrogate_key(df: pd.DataFrame, sk_name: str) -> pd.DataFrame:
    df = df.reset_index(drop=True).copy()
    df[sk_name] = range(1, len(df) + 1)
    cols = [sk_name] + [c for c in df.columns if c != sk_name]
    return df[cols]


def build_calendar_dimension(order_dates: pd.Series, ship_dates: pd.Series) -> pd.DataFrame:
    all_dates = pd.concat([order_dates, ship_dates], ignore_index=True)
    all_dates = pd.to_datetime(all_dates, errors="coerce").dropna().drop_duplicates().sort_values()

    d = pd.DataFrame({"full_date": all_dates})
    d["date_sk"] = d["full_date"].dt.strftime("%Y%m%d").astype(int)
    d["year"] = d["full_date"].dt.year
    d["quarter"] = d["full_date"].dt.quarter
    d["month_num"] = d["full_date"].dt.month
    d["month_name"] = d["full_date"].dt.month_name()
    d["month_short"] = d["full_date"].dt.strftime("%b")
    d["year_month"] = d["full_date"].dt.strftime("%Y-%m")
    d["year_month_sort"] = d["full_date"].dt.year * 100 + d["full_date"].dt.month
    d["week_num"] = d["full_date"].dt.isocalendar().week.astype(int)
    d["day_num"] = d["full_date"].dt.day
    d["day_name"] = d["full_date"].dt.day_name()
    d["is_weekend"] = d["full_date"].dt.dayofweek.isin([5, 6])

    return d[
        [
            "date_sk",
            "full_date",
            "year",
            "quarter",
            "month_num",
            "month_name",
            "month_short",
            "year_month",
            "year_month_sort",
            "week_num",
            "day_num",
            "day_name",
            "is_weekend",
        ]
    ].copy()


def discount_band(x: float) -> str:
    if pd.isna(x):
        return "Unknown"
    if x == 0:
        return "No Discount"
    if x <= 0.10:
        return "Low"
    if x <= 0.20:
        return "Medium"
    if x <= 0.30:
        return "High"
    return "Very High"


def profitability_band(x: float) -> str:
    if pd.isna(x):
        return "Unknown"
    if x < 0:
        return "Loss"
    if x < 0.10:
        return "Low Margin"
    if x < 0.20:
        return "Medium Margin"
    return "High Margin"


# ============================================
# LEITURA DA BASE
# ============================================
print("Lendo arquivo raw...")
df = pd.read_csv(RAW_FILE, encoding="latin1")
raw_row_count = len(df)
print(f"Linhas lidas: {raw_row_count:,}")
print(f"Colunas lidas: {len(df.columns)}")

# ============================================
# PADRONIZAÇÃO DOS NOMES DE COLUNAS
# ============================================
df.columns = [normalize_column_name(c) for c in df.columns]

expected_columns = {
    "category",
    "city",
    "country",
    "customer_id",
    "customer_name",
    "discount",
    "market",
    "order_date",
    "order_id",
    "order_priority",
    "product_id",
    "product_name",
    "profit",
    "quantity",
    "region",
    "row_id",
    "sales",
    "segment",
    "ship_date",
    "ship_mode",
    "shipping_cost",
    "state",
    "sub_category",
    "year",
    "market2",
    "weeknum",
}

weird_cols = [c for c in df.columns if c not in expected_columns]
if weird_cols:
    print(f"Colunas não mapeadas detectadas: {weird_cols}")

if len(weird_cols) == 1:
    df = df.rename(columns={weird_cols[0]: "record_count"})
elif len(weird_cols) > 1:
    rename_map = {c: f"extra_col_{i+1}" for i, c in enumerate(weird_cols)}
    df = df.rename(columns=rename_map)

print("\nColunas após padronização:")
print(df.columns.tolist())

# ============================================
# TRATAMENTO DE TIPOS
# ============================================
print("\nTratando tipos...")

text_cols = [
    "category",
    "city",
    "country",
    "customer_id",
    "customer_name",
    "market",
    "order_id",
    "order_priority",
    "product_id",
    "product_name",
    "region",
    "segment",
    "ship_mode",
    "state",
    "sub_category",
    "market2",
]

for col in text_cols:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip()

numeric_cols_int = ["quantity", "row_id", "year", "weeknum"]
for col in numeric_cols_int:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

numeric_cols_decimal = ["discount", "profit", "sales", "shipping_cost"]
for col in numeric_cols_decimal:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

for col in ["order_date", "ship_date"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# ============================================
# TRATAMENTO BÁSICO DE QUALIDADE
# ============================================
print("\nAplicando regras de qualidade...")

if "row_id" in df.columns:
    before = len(df)
    df = df.drop_duplicates(subset=["row_id"]).copy()
    after = len(df)
    print(f"Duplicidades removidas por row_id: {before - after}")

required_cols = ["row_id", "order_id", "order_date", "ship_date", "customer_id", "product_id"]
before = len(df)
df = df.dropna(subset=[c for c in required_cols if c in df.columns]).copy()
after = len(df)
print(f"Linhas removidas por falta de campos críticos: {before - after}")

for col in text_cols:
    if col in df.columns:
        df[col] = df[col].replace("", pd.NA).fillna("Unknown")

for col in ["discount", "profit", "sales", "shipping_cost"]:
    if col in df.columns:
        df[col] = df[col].fillna(0)

if "quantity" in df.columns:
    df["quantity"] = df["quantity"].fillna(0).astype(int)

if "row_id" in df.columns:
    df["row_id"] = df["row_id"].astype(int)

print(f"Linhas após limpeza: {len(df):,}")

# ============================================
# COLUNAS DERIVADAS
# ============================================
print("\nGerando colunas derivadas...")

df["order_date_sk"] = df["order_date"].dt.strftime("%Y%m%d").astype(int)
df["ship_date_sk"] = df["ship_date"].dt.strftime("%Y%m%d").astype(int)
df["days_to_ship"] = (df["ship_date"] - df["order_date"]).dt.days
df["days_to_ship"] = df["days_to_ship"].fillna(0).astype(int)

df["sales_amount"] = df["sales"].round(2)
df["profit_amount"] = df["profit"].round(2)
df["quantity_sold"] = df["quantity"].astype(int)
df["discount_rate"] = df["discount"].round(4)
df["shipping_cost_amount"] = df["shipping_cost"].round(2)

df["margin_pct"] = df.apply(
    lambda x: round(x["profit_amount"] / x["sales_amount"], 4) if x["sales_amount"] not in [0, None] else None,
    axis=1,
)

df["order_line_count"] = 1
df["profitable_flag"] = df["profit_amount"] > 0

df["discount_band"] = df["discount_rate"].apply(discount_band)
df["profitability_band"] = df["margin_pct"].apply(profitability_band)

# ============================================
# SALVAR STAGING LIMPO
# ============================================
staging_file = STAGING_DIR / "superstore_staging.csv"
df.to_csv(staging_file, index=False, encoding="utf-8-sig")
print(f"\nArquivo staging salvo em: {staging_file}")

# ============================================
# CONSTRUÇÃO DAS DIMENSÕES
# ============================================
print("\nConstruindo dimensões...")

d_calendar = build_calendar_dimension(df["order_date"], df["ship_date"])

d_customer = (
    df[["customer_id", "customer_name", "segment"]]
    .sort_values(["customer_id", "customer_name", "segment"])
    .drop_duplicates(subset=["customer_id"], keep="first")
    .reset_index(drop=True)
)
d_customer = add_surrogate_key(d_customer, "customer_sk")

d_product = (
    df[["product_id", "product_name", "category", "sub_category"]]
    .sort_values(["product_id", "product_name", "category", "sub_category"])
    .drop_duplicates(subset=["product_id"], keep="first")
    .reset_index(drop=True)
)
d_product = add_surrogate_key(d_product, "product_sk")

d_geography = (
    df[["country", "region", "state", "city"]]
    .drop_duplicates()
    .sort_values(["country", "region", "state", "city"])
    .reset_index(drop=True)
)
d_geography = add_surrogate_key(d_geography, "geography_sk")

d_market = (
    df[["market", "market2"]]
    .sort_values(["market", "market2"])
    .drop_duplicates(subset=["market"], keep="first")
    .reset_index(drop=True)
)
d_market = add_surrogate_key(d_market, "market_sk")

d_ship_mode = (
    df[["ship_mode"]]
    .drop_duplicates()
    .sort_values(["ship_mode"])
    .reset_index(drop=True)
)
d_ship_mode = add_surrogate_key(d_ship_mode, "ship_mode_sk")

d_order_priority = (
    df[["order_priority"]]
    .drop_duplicates()
    .sort_values(["order_priority"])
    .reset_index(drop=True)
)
d_order_priority = add_surrogate_key(d_order_priority, "order_priority_sk")

d_discount_band = (
    df[["discount_band"]]
    .drop_duplicates()
    .sort_values(["discount_band"])
    .reset_index(drop=True)
)
d_discount_band = add_surrogate_key(d_discount_band, "discount_band_sk")

d_profitability_band = (
    df[["profitability_band"]]
    .drop_duplicates()
    .sort_values(["profitability_band"])
    .reset_index(drop=True)
)
d_profitability_band = add_surrogate_key(d_profitability_band, "profitability_band_sk")

# ============================================
# CONSTRUÇÃO DA FATO
# ============================================
print("Construindo tabela fato...")

fact = df.copy()

fact = fact.merge(
    d_customer[["customer_sk", "customer_id"]],
    on="customer_id",
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_product[["product_sk", "product_id"]],
    on="product_id",
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_geography[["geography_sk", "country", "region", "state", "city"]],
    on=["country", "region", "state", "city"],
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_market[["market_sk", "market"]],
    on=["market"],
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_ship_mode[["ship_mode_sk", "ship_mode"]],
    on="ship_mode",
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_order_priority[["order_priority_sk", "order_priority"]],
    on="order_priority",
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_discount_band[["discount_band_sk", "discount_band"]],
    on="discount_band",
    how="left",
    validate="many_to_one"
)

fact = fact.merge(
    d_profitability_band[["profitability_band_sk", "profitability_band"]],
    on="profitability_band",
    how="left",
    validate="many_to_one"
)

f_sales_order_line = fact[
    [
        "row_id",
        "order_id",
        "order_date_sk",
        "ship_date_sk",
        "customer_sk",
        "product_sk",
        "geography_sk",
        "market_sk",
        "ship_mode_sk",
        "order_priority_sk",
        "discount_band_sk",
        "profitability_band_sk",
        "sales_amount",
        "profit_amount",
        "quantity_sold",
        "discount_rate",
        "shipping_cost_amount",
        "days_to_ship",
        "margin_pct",
        "order_line_count",
        "profitable_flag",
    ]
].copy()

f_sales_order_line = f_sales_order_line.rename(
    columns={
        "row_id": "row_id_bk",
        "order_id": "order_id_bk",
        "shipping_cost_amount": "shipping_cost",
    }
)

f_sales_order_line = add_surrogate_key(f_sales_order_line, "sales_line_sk")

# ============================================
# VALIDAÇÕES CRÍTICAS
# ============================================
print("\nValidando chaves nulas nas dimensões e fato...")

fk_cols = [
    "order_date_sk",
    "ship_date_sk",
    "customer_sk",
    "product_sk",
    "geography_sk",
    "market_sk",
    "ship_mode_sk",
    "order_priority_sk",
    "discount_band_sk",
    "profitability_band_sk",
]

null_fk_report = {col: int(f_sales_order_line[col].isna().sum()) for col in fk_cols}
print(null_fk_report)

print("\nValidando granularidade da fato...")
print(f"Linhas raw limpas: {len(df):,}")
print(f"Linhas fato: {len(f_sales_order_line):,}")

if len(df) != len(f_sales_order_line):
    raise ValueError(
        f"ERRO: a fato ficou com {len(f_sales_order_line):,} linhas, "
        f"mas a base limpa tem {len(df):,}. Houve multiplicação indevida."
    )

duplicated_row_id = int(f_sales_order_line["row_id_bk"].duplicated().sum())
print(f"Duplicidades de row_id_bk na fato: {duplicated_row_id}")

if duplicated_row_id > 0:
    raise ValueError(
        f"ERRO: existem {duplicated_row_id} row_id_bk duplicados na fato."
    )

# ============================================
# EXPORTAR CURATED
# ============================================
print("\nSalvando arquivos curated...")

d_calendar.to_csv(CURATED_DIR / "d_calendar.csv", index=False, encoding="utf-8-sig")
d_customer.to_csv(CURATED_DIR / "d_customer.csv", index=False, encoding="utf-8-sig")
d_product.to_csv(CURATED_DIR / "d_product.csv", index=False, encoding="utf-8-sig")
d_geography.to_csv(CURATED_DIR / "d_geography.csv", index=False, encoding="utf-8-sig")
d_market.to_csv(CURATED_DIR / "d_market.csv", index=False, encoding="utf-8-sig")
d_ship_mode.to_csv(CURATED_DIR / "d_ship_mode.csv", index=False, encoding="utf-8-sig")
d_order_priority.to_csv(CURATED_DIR / "d_order_priority.csv", index=False, encoding="utf-8-sig")
d_discount_band.to_csv(CURATED_DIR / "d_discount_band.csv", index=False, encoding="utf-8-sig")
d_profitability_band.to_csv(CURATED_DIR / "d_profitability_band.csv", index=False, encoding="utf-8-sig")
f_sales_order_line.to_csv(CURATED_DIR / "f_sales_order_line.csv", index=False, encoding="utf-8-sig")

# ============================================
# RELATÓRIO DE QUALIDADE
# ============================================
quality_report = pd.DataFrame(
    {
        "table_name": [
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
        ],
        "row_count": [
            len(d_calendar),
            len(d_customer),
            len(d_product),
            len(d_geography),
            len(d_market),
            len(d_ship_mode),
            len(d_order_priority),
            len(d_discount_band),
            len(d_profitability_band),
            len(f_sales_order_line),
        ],
    }
)

quality_report.to_csv(LOGS_DIR / "quality_report.csv", index=False, encoding="utf-8-sig")

# ============================================
# RESUMO FINAL
# ============================================
print("\n================ RESUMO FINAL ================")
print(f"Staging: {staging_file}")
print(f"Curated: {CURATED_DIR}")
print(f"Logs: {LOGS_DIR}")
print("\nQuantidade de registros por tabela:")
print(quality_report.to_string(index=False))

print("\nPrimeiras linhas da fato:")
print(f_sales_order_line.head())

print("\nProcesso ETL local concluído com sucesso.")