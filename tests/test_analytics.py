import sqlite3

from src.analytics import run_analytics


def test_top_store_net_revenue_includes_returns(tmp_path) -> None:
    warehouse = tmp_path / "warehouse.db"
    sql_file = tmp_path / "analytics.sql"
    sql_file.write_text(
        """
-- name: top_5_stores_by_net_revenue
WITH bounds AS (
    SELECT date(MAX(date_key), '-29 days') AS start_date, MAX(date_key) AS end_date
    FROM fact_sales
)
SELECT
    s.store_id,
    s.store_name,
    s.region,
    ROUND(SUM(f.total_amount), 2) AS net_revenue,
    COUNT(*) AS transaction_count
FROM fact_sales f
JOIN dim_store s ON s.store_id = f.store_id
JOIN bounds b ON f.date_key BETWEEN b.start_date AND b.end_date
GROUP BY s.store_id, s.store_name, s.region
ORDER BY net_revenue DESC
LIMIT 5;
"""
    )

    with sqlite3.connect(warehouse) as conn:
        conn.executescript(
            """
            CREATE TABLE dim_store (
                store_id TEXT PRIMARY KEY,
                store_name TEXT,
                region TEXT
            );
            CREATE TABLE fact_sales (
                transaction_id TEXT PRIMARY KEY,
                date_key TEXT,
                store_id TEXT,
                total_amount REAL
            );
            INSERT INTO dim_store VALUES ('S001', 'Store One', 'East');
            INSERT INTO dim_store VALUES ('S002', 'Store Two', 'West');
            INSERT INTO fact_sales VALUES ('T001', '2026-06-01', 'S001', 100.0);
            INSERT INTO fact_sales VALUES ('T002', '2026-06-02', 'S001', -25.0);
            INSERT INTO fact_sales VALUES ('T003', '2026-06-02', 'S002', 50.0);
            """
        )

    results = run_analytics(warehouse_path=warehouse, sql_path=sql_file)

    assert results["top_5_stores_by_net_revenue"][0]["store_id"] == "S001"
    assert results["top_5_stores_by_net_revenue"][0]["net_revenue"] == 75.0
