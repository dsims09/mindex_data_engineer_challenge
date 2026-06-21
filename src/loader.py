from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.cleaner import CleanedData
from src.paths import SQL_DIR, WAREHOUSE_PATH


def _date_dimension(transaction_dates: pd.Series) -> pd.DataFrame:
    dates = pd.to_datetime(transaction_dates).dropna()
    if dates.empty:
        return pd.DataFrame(
            columns=[
                "date_key",
                "full_date",
                "year",
                "quarter",
                "month",
                "month_name",
                "day",
                "day_of_week",
                "day_name",
                "is_weekend",
            ]
        )

    calendar = pd.date_range(dates.min(), dates.max(), freq="D")
    return pd.DataFrame(
        {
            "date_key": calendar.strftime("%Y-%m-%d"),
            "full_date": calendar.strftime("%Y-%m-%d"),
            "year": calendar.year,
            "quarter": calendar.quarter,
            "month": calendar.month,
            "month_name": calendar.strftime("%B"),
            "day": calendar.day,
            "day_of_week": calendar.dayofweek + 1,
            "day_name": calendar.strftime("%A"),
            "is_weekend": calendar.dayofweek.isin([5, 6]).astype(int),
        }
    )


def load_warehouse(
    cleaned: CleanedData,
    warehouse_path: Path = WAREHOUSE_PATH,
    schema_path: Path = SQL_DIR / "schema.sql",
) -> None:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    if warehouse_path.exists():
        warehouse_path.unlink()

    with sqlite3.connect(warehouse_path) as conn:
        conn.executescript(schema_path.read_text())

        dim_store = cleaned.stores[
            ["store_id", "store_name", "city", "state", "zip_code", "region", "opened_date"]
        ].copy()
        dim_store.to_sql("dim_store", conn, if_exists="append", index=False)

        dim_product = cleaned.products[
            [
                "product_id",
                "product_name",
                "category",
                "catalog_unit_price",
                "supplier_id",
                "has_catalog_price_conflict",
                "has_zero_catalog_price",
            ]
        ].copy()
        dim_product["has_catalog_price_conflict"] = dim_product["has_catalog_price_conflict"].astype(int)
        dim_product["has_zero_catalog_price"] = dim_product["has_zero_catalog_price"].astype(int)
        dim_product.to_sql("dim_product", conn, if_exists="append", index=False)

        dim_date = _date_dimension(cleaned.transactions["transaction_date"])
        dim_date.to_sql("dim_date", conn, if_exists="append", index=False)

        fact_sales = cleaned.transactions[
            [
                "transaction_id",
                "transaction_date",
                "store_id",
                "product_id",
                "customer_id",
                "is_guest_customer",
                "quantity",
                "unit_price",
                "total_amount",
                "is_return",
                "has_amount_mismatch",
            ]
        ].copy()
        fact_sales = fact_sales.rename(columns={"transaction_date": "date_key"})
        for column in ["is_guest_customer", "is_return", "has_amount_mismatch"]:
            fact_sales[column] = fact_sales[column].astype(int)
        fact_sales.to_sql("fact_sales", conn, if_exists="append", index=False)
