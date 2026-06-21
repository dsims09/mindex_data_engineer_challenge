from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from src.analytics import write_analytics
from src.cleaner import clean_all
from src.loader import load_warehouse
from src.paths import (
    ANALYTICS_PATH,
    DATA_DIR,
    DATA_QUALITY_REPORT_PATH,
    OUTPUT_DIR,
    PROFILING_REPORT_PATH,
    WAREHOUSE_PATH,
)
from src.profiler import profile


DEFAULT_PROCESSING_DATE = date(2026, 6, 2)


def load_raw_data() -> dict[str, pd.DataFrame]:
    return {
        "stores": pd.read_csv(DATA_DIR / "stores.csv", dtype={"store_id": "string", "zip_code": "string"}),
        "products": pd.read_csv(
            DATA_DIR / "products.csv",
            dtype={"product_id": "string", "product_name": "string", "category": "string", "supplier_id": "string"},
        ),
        "transactions": pd.read_csv(
            DATA_DIR / "transactions.csv",
            dtype={
                "transaction_id": "string",
                "transaction_date": "string",
                "store_id": "string",
                "product_id": "string",
                "customer_id": "string",
            },
        ),
    }


def _write_json(path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def run_pipeline(as_of_date: date | None = None) -> dict[str, Any]:
    as_of_date = as_of_date or DEFAULT_PROCESSING_DATE
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_data = load_raw_data()
    profiling_report = {
        name: profile(df, name=name, as_of_date=as_of_date)
        for name, df in raw_data.items()
    }
    _write_json(PROFILING_REPORT_PATH, profiling_report)

    cleaned = clean_all(raw_data, as_of_date=as_of_date)
    _write_json(DATA_QUALITY_REPORT_PATH, cleaned.data_quality_report)

    load_warehouse(cleaned, warehouse_path=WAREHOUSE_PATH)
    analytics = write_analytics(warehouse_path=WAREHOUSE_PATH, output_path=ANALYTICS_PATH)

    return {
        "profiling_report": PROFILING_REPORT_PATH,
        "data_quality_report": DATA_QUALITY_REPORT_PATH,
        "warehouse": WAREHOUSE_PATH,
        "analytics": ANALYTICS_PATH,
        "analytics_results": analytics,
    }


def main() -> None:
    results = run_pipeline()
    print("Generated pipeline artifacts:")
    for key in ["profiling_report", "data_quality_report", "warehouse", "analytics"]:
        print(f"- {results[key]}")


if __name__ == "__main__":
    main()
