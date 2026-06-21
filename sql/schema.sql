PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_date (
    date_key TEXT PRIMARY KEY,
    full_date TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend INTEGER NOT NULL
);

CREATE TABLE dim_store (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    region TEXT NOT NULL,
    opened_date TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    catalog_unit_price REAL NOT NULL,
    supplier_id TEXT NOT NULL,
    has_catalog_price_conflict INTEGER NOT NULL,
    has_zero_catalog_price INTEGER NOT NULL
);

CREATE TABLE fact_sales (
    transaction_id TEXT PRIMARY KEY,
    date_key TEXT NOT NULL,
    store_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    customer_id TEXT,
    is_guest_customer INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_amount REAL NOT NULL,
    is_return INTEGER NOT NULL,
    has_amount_mismatch INTEGER NOT NULL,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

CREATE INDEX idx_fact_sales_store ON fact_sales(store_id);
CREATE INDEX idx_fact_sales_product ON fact_sales(product_id);
CREATE INDEX idx_fact_sales_customer ON fact_sales(customer_id);
CREATE INDEX idx_fact_sales_date ON fact_sales(date_key);
