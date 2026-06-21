# Mindex Data Engineer Challenge

## Overview

This solution builds a small retail analytics warehouse from three raw CSV exports. The pipeline profiles the source files, applies documented cleaning rules, loads a SQLite star schema, and answers the requested business questions from the modeled warehouse.

The original challenge prompt is preserved in [CHALLENGE.md](CHALLENGE.md).

## Architecture

```text
data/raw/*.csv
      |
      v
src/profiler.py       -> output/profiling_report.json
      |
      v
src/cleaner.py        -> output/data_quality_report.json
      |
      v
sql/schema.sql
src/loader.py         -> output/warehouse.db
      |
      v
sql/analytics.sql
src/analytics.py      -> output/analytics.json
```

Pandas is used for profiling and deterministic source cleanup. SQLite SQL is used for the final analytics so the business answers come from the same warehouse model a downstream consumer would query.

## Setup and Run

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline
python -m pytest
```

The pipeline generates these local artifacts:

```text
output/profiling_report.json
output/data_quality_report.json
output/warehouse.db
output/analytics.json
```

Generated output files are intentionally ignored by git so the repository stays source-focused and repeatable.

For reproducibility, the pipeline uses a default processing date of 2026-06-02, based on the provided extract context. In a production pipeline this would usually be an execution parameter or derived from extract metadata.

## Data Quality Findings

Counts below are from the current pipeline run. Future-dated transaction counts are evaluated relative to the deterministic processing date.

| Issue | File | Count | Decision | Rationale |
|---|---:|---:|---|---|
| Malformed ZIP code | stores.csv | 1 | Standardized numeric ZIP values to five characters with leading zeros. | ZIP codes are identifiers, not numbers, so leading zeros are significant. |
| Missing region | stores.csv | 2 | Set missing regions to Unknown. | The source does not contain enough information to infer the business region reliably. |
| Duplicate store_id with conflicting name | stores.csv | 1 | Kept the first store record for each store_id. | The warehouse requires one row per store, and the duplicate row matches the same location attributes. |
| Exact duplicate product row | products.csv | 1 | Dropped exact duplicate rows. | Exact duplicates add no new product information and can cause dimension key ambiguity. |
| Missing product category | products.csv | 5 | Set missing categories to Uncategorized. | The product can still be sold and analyzed without inventing a category. |
| Product has multiple catalog prices | products.csv | 1 | Kept one product dimension row and flagged the catalog price conflict. | Revenue should come from transaction unit_price and total_amount, not a possibly stale catalog price. |
| Zero catalog unit price | products.csv | 1 | Kept the product and flagged the suspicious catalog price. | Transactions for this product contain real prices, so excluding the product would lose valid sales. |
| Mixed transaction date formats | transactions.csv | 20 | Standardized parseable dates to ISO format. | The values are parseable dates representing the same business attribute. |
| Currency-formatted total_amount values | transactions.csv | 25 | Removed currency symbols and converted total_amount to numeric. | The format is inconsistent, but the amount value is usable. |
| Exact duplicate transaction row | transactions.csv | 15 | Dropped exact duplicate rows before warehouse load. | Duplicate transaction IDs and identical values would overstate sales. |
| Missing customer_id | transactions.csv | 40 | Preserved the transaction and flagged it as a guest customer. | Guest transactions are valid sales but should be excluded from customer lifetime spend. |
| Return transaction | transactions.csv | 30 | Preserved returns as negative fact rows. | Returns reduce net revenue and are required for accurate business reporting. |
| Transaction amount differs from quantity times unit_price | transactions.csv | 20 | Preserved the source total_amount and flagged the mismatch. | The mismatch may represent discounts or source pricing logic that should not be overwritten. |
| Transaction references unknown store_id | transactions.csv | 5 | Excluded from fact_sales. | The fact table requires a valid store foreign key for trusted warehouse analytics. |
| Transaction references unknown product_id | transactions.csv | 3 | Excluded from fact_sales. | The fact table requires a valid product foreign key for trusted warehouse analytics. |
| Zero quantity transaction | transactions.csv | 5 | Excluded from fact_sales. | Zero quantity rows do not represent sales or returns and can distort transaction counts. |
| Future-dated transaction | transactions.csv | 3 | Excluded from fact_sales. | Future-dated rows are not part of historical sales reporting as of the processing date. |

## Warehouse Schema

The warehouse is loaded to `output/warehouse.db` using the schema in `sql/schema.sql`.

| Table | Grain | Notes |
|---|---|---|
| dim_date | One row per calendar date in the transaction window | Includes year, quarter, month, day, weekday, and weekend attributes. |
| dim_store | One row per store_id | Store duplicate IDs are deduplicated before load. Missing regions are represented as Unknown. |
| dim_product | One row per product_id | Product catalog price conflicts and zero catalog prices are retained as flags. |
| fact_sales | One row per valid transaction | Contains store, product, date, customer_id, quantity, unit_price, total_amount, return flag, guest flag, and amount mismatch flag. |

Loaded warehouse row counts from the current run:

| Table | Rows |
|---|---:|
| dim_date | 89 |
| dim_store | 15 |
| dim_product | 30 |
| fact_sales | 474 |

## Modeling Decisions

Products with more than one price on record are kept as one product dimension row with `has_catalog_price_conflict = 1`. The selected catalog price is deterministic, but revenue calculations use transaction-level `total_amount` and `unit_price` because those fields represent the actual sale.

Returns are preserved in `fact_sales` as negative quantity and negative amount rows with `is_return = 1`. They reduce net revenue and are included in return-rate calculations.

Guest or anonymous transactions are preserved with `is_guest_customer = 1` and `customer_id` left null. They are excluded only from customer lifetime spend analytics.

Transactions are excluded from `fact_sales` when they cannot satisfy the warehouse grain and keys: unknown store, unknown product, zero quantity, invalid date or amount, or future date relative to the processing date.

## Analytics

Analytics are defined in `sql/analytics.sql` and written to `output/analytics.json`.

Month-over-month results use calendar months from the available data, so the first and last months may be partial depending on the transaction window.

The five outputs are:

| Output key | Business question |
|---|---|
| top_5_stores_by_net_revenue | Top stores by net revenue in the most recent 30-day data window. |
| month_over_month_revenue_change_by_category | Net revenue and percent change by product category and month. |
| return_rate_by_store | Return transactions divided by total transactions, with a flag above 10 percent. |
| average_transaction_value_by_region | Average non-return transaction value by region. |
| top_10_customers_by_lifetime_spend | Highest non-guest customer spend, with transaction count and average order value. |

## Tests

The test suite covers:

| Area | Coverage |
|---|---|
| Profiling | Empty DataFrame handling, all-null columns, numeric zero and negative counts. |
| Cleaning | Store ZIP and duplicate handling, product conflict flags, transaction exclusions and return preservation. |
| Analytics | SQLite fixture validating that returns reduce net revenue in the top-store query. |

Run with:

```bash
python -m pytest
```

## Key Design Decisions

- Returns are valid business events and should reduce revenue rather than be filtered out.
- Orphaned store and product transactions are excluded from `fact_sales` because they would break trusted dimensional analytics.
- Transaction `total_amount` drives revenue because catalog prices can be stale or conflicting.
- `customer_id` stays in `fact_sales` because there is no customer reference source to support a meaningful customer dimension.
- Data quality issues are standardized or flagged when deterministic, and excluded only when they break the warehouse grain or keys.
- Analytics are run from SQLite SQL against the modeled warehouse rather than from one-off pandas transformations.

## Productionization Notes

With more time, I would add orchestration, incremental load support, and stronger observability:

- Schedule the pipeline with a workflow tool such as Airflow, Dagster, or a managed cloud scheduler.
- Add source file arrival checks, schema drift checks, and row-count alerts.
- Persist rejected transaction records with exclusion reasons for operational review.
- Add data quality thresholds that fail the run when critical issue counts exceed expected ranges.
- Add warehouse migration management instead of recreating the SQLite database on each run.
- Partition incremental loads by transaction date and make the fact load idempotent by transaction_id.
- Publish analytics outputs to a durable reporting location.

## With More Time

I would expand tests around every exclusion reason, add a rejected-records output, and make the processing date configurable from the command line. I would also add a simple ER diagram and a small data dictionary for each warehouse column.
