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

-- name: month_over_month_revenue_change_by_category
WITH monthly AS (
    SELECT
        p.category,
        SUBSTR(f.date_key, 1, 7) AS sales_month,
        ROUND(SUM(f.total_amount), 2) AS net_revenue
    FROM fact_sales f
    JOIN dim_product p ON p.product_id = f.product_id
    GROUP BY p.category, SUBSTR(f.date_key, 1, 7)
),
with_previous AS (
    SELECT
        category,
        sales_month,
        net_revenue,
        LAG(net_revenue) OVER (PARTITION BY category ORDER BY sales_month) AS previous_month_revenue
    FROM monthly
)
SELECT
    category,
    sales_month,
    net_revenue,
    previous_month_revenue,
    CASE
        WHEN previous_month_revenue IS NULL OR previous_month_revenue = 0 THEN NULL
        ELSE ROUND(((net_revenue - previous_month_revenue) / previous_month_revenue) * 100, 2)
    END AS revenue_change_pct
FROM with_previous
ORDER BY category, sales_month;

-- name: return_rate_by_store
SELECT
    s.store_id,
    s.store_name,
    s.region,
    COUNT(*) AS total_transactions,
    SUM(CASE WHEN f.is_return = 1 THEN 1 ELSE 0 END) AS return_transactions,
    ROUND(CAST(SUM(CASE WHEN f.is_return = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*), 4) AS return_rate,
    CASE
        WHEN CAST(SUM(CASE WHEN f.is_return = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) > 0.10 THEN 1
        ELSE 0
    END AS exceeds_10_percent
FROM fact_sales f
JOIN dim_store s ON s.store_id = f.store_id
GROUP BY s.store_id, s.store_name, s.region
ORDER BY return_rate DESC, s.store_id;

-- name: average_transaction_value_by_region
SELECT
    s.region,
    COUNT(*) AS transaction_count,
    ROUND(SUM(f.total_amount), 2) AS gross_revenue,
    ROUND(AVG(f.total_amount), 2) AS average_transaction_value
FROM fact_sales f
JOIN dim_store s ON s.store_id = f.store_id
WHERE f.is_return = 0
GROUP BY s.region
ORDER BY average_transaction_value DESC;

-- name: top_10_customers_by_lifetime_spend
SELECT
    f.customer_id,
    ROUND(SUM(f.total_amount), 2) AS lifetime_spend,
    COUNT(*) AS transaction_count,
    ROUND(AVG(f.total_amount), 2) AS average_order_value
FROM fact_sales f
WHERE f.is_guest_customer = 0
  AND f.customer_id IS NOT NULL
GROUP BY f.customer_id
ORDER BY lifetime_spend DESC
LIMIT 10;
