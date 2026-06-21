from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.paths import ANALYTICS_PATH, SQL_DIR, WAREHOUSE_PATH


def load_named_queries(sql_path: Path = SQL_DIR / "analytics.sql") -> dict[str, str]:
    queries: dict[str, list[str]] = {}
    current_name: str | None = None

    for line in sql_path.read_text().splitlines():
        if line.startswith("-- name:"):
            current_name = line.replace("-- name:", "", 1).strip()
            queries[current_name] = []
            continue
        if current_name is not None:
            queries[current_name].append(line)

    return {name: "\n".join(lines).strip().rstrip(";") for name, lines in queries.items()}


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records"))


def run_analytics(
    warehouse_path: Path = WAREHOUSE_PATH,
    sql_path: Path = SQL_DIR / "analytics.sql",
) -> dict[str, list[dict[str, Any]]]:
    queries = load_named_queries(sql_path)
    results: dict[str, list[dict[str, Any]]] = {}

    with sqlite3.connect(warehouse_path) as conn:
        for name, query in queries.items():
            results[name] = _records(pd.read_sql_query(query, conn))

    return results


def write_analytics(
    warehouse_path: Path = WAREHOUSE_PATH,
    output_path: Path = ANALYTICS_PATH,
    sql_path: Path = SQL_DIR / "analytics.sql",
) -> dict[str, list[dict[str, Any]]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = run_analytics(warehouse_path=warehouse_path, sql_path=sql_path)
    output_path.write_text(json.dumps(results, indent=2))
    return results
