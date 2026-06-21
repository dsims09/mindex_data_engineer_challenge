from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from src.profiler import parse_mixed_dates


@dataclass(frozen=True)
class CleanedData:
    stores: pd.DataFrame
    products: pd.DataFrame
    transactions: pd.DataFrame
    data_quality_report: list[dict[str, Any]]


def _issue(issue: str, file_name: str, count: int, decision: str, rationale: str) -> dict[str, Any]:
    return {
        "issue": issue,
        "file": file_name,
        "count": int(count),
        "decision": decision,
        "rationale": rationale,
    }


def clean_stores(stores: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    df = stores.copy()
    issues: list[dict[str, Any]] = []

    malformed_zip = ~df["zip_code"].astype("string").str.fullmatch(r"\d{5}", na=False)
    issues.append(
        _issue(
            "Malformed ZIP code",
            "stores.csv",
            int(malformed_zip.sum()),
            "Standardized numeric ZIP values to five characters with leading zeros.",
            "ZIP codes are identifiers, not numbers, so leading zeros are significant.",
        )
    )
    df["zip_code"] = df["zip_code"].astype("string").str.strip().str.zfill(5)

    missing_region = df["region"].isna()
    issues.append(
        _issue(
            "Missing region",
            "stores.csv",
            int(missing_region.sum()),
            "Set missing regions to Unknown.",
            "The source does not contain enough information to infer the business region reliably.",
        )
    )
    df["region"] = df["region"].fillna("Unknown")

    duplicate_store_rows = int(df.duplicated("store_id", keep="first").sum())
    issues.append(
        _issue(
            "Duplicate store_id with conflicting name",
            "stores.csv",
            duplicate_store_rows,
            "Kept the first store record for each store_id.",
            "The warehouse requires one row per store, and the duplicate row matches the same location attributes.",
        )
    )
    df = df.drop_duplicates("store_id", keep="first").reset_index(drop=True)

    df["opened_date"] = parse_mixed_dates(df["opened_date"]).dt.date.astype("string")
    return df, issues


def clean_products(products: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    df = products.copy()
    issues: list[dict[str, Any]] = []

    exact_duplicates = int(df.duplicated().sum())
    issues.append(
        _issue(
            "Exact duplicate product row",
            "products.csv",
            exact_duplicates,
            "Dropped exact duplicate rows.",
            "Exact duplicates add no new product information and can cause dimension key ambiguity.",
        )
    )
    df = df.drop_duplicates().reset_index(drop=True)

    missing_category = df["category"].isna()
    issues.append(
        _issue(
            "Missing product category",
            "products.csv",
            int(missing_category.sum()),
            "Set missing categories to Uncategorized.",
            "The product can still be sold and analyzed without inventing a category.",
        )
    )
    df["category"] = df["category"].fillna("Uncategorized")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")

    price_counts = df.groupby("product_id")["unit_price"].nunique(dropna=True)
    price_conflict_ids = set(price_counts[price_counts > 1].index)
    conflict_extra_rows = int(df[df["product_id"].isin(price_conflict_ids)].shape[0] - len(price_conflict_ids))
    issues.append(
        _issue(
            "Product has multiple catalog prices",
            "products.csv",
            conflict_extra_rows,
            "Kept one product dimension row and flagged the catalog price conflict.",
            "Revenue should come from transaction unit_price and total_amount, not a possibly stale catalog price.",
        )
    )

    zero_price_ids = set(df.loc[df["unit_price"] == 0, "product_id"])
    issues.append(
        _issue(
            "Zero catalog unit price",
            "products.csv",
            len(zero_price_ids),
            "Kept the product and flagged the suspicious catalog price.",
            "Transactions for this product contain real prices, so excluding the product would lose valid sales.",
        )
    )

    df["has_catalog_price_conflict"] = df["product_id"].isin(price_conflict_ids)
    df["has_zero_catalog_price"] = df["product_id"].isin(zero_price_ids)
    df = df.sort_values(["product_id", "unit_price"], ascending=[True, False])
    df = df.drop_duplicates("product_id", keep="first").reset_index(drop=True)
    df = df.rename(columns={"unit_price": "catalog_unit_price"})

    return df, issues


def clean_transactions(
    transactions: pd.DataFrame,
    valid_store_ids: set[str],
    valid_product_ids: set[str],
    as_of_date: date | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    as_of_date = as_of_date or date.today()
    df = transactions.copy()
    issues: list[dict[str, Any]] = []

    mixed_date_formats = ~df["transaction_date"].astype("string").str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)
    issues.append(
        _issue(
            "Mixed transaction date formats",
            "transactions.csv",
            int(mixed_date_formats.sum()),
            "Standardized parseable dates to ISO format.",
            "The values are parseable dates representing the same business attribute.",
        )
    )
    parsed_dates = parse_mixed_dates(df["transaction_date"])
    df["transaction_date"] = parsed_dates.dt.date.astype("string")

    currency_amounts = df["total_amount"].astype("string").str.contains(r"^\$", na=False)
    issues.append(
        _issue(
            "Currency-formatted total_amount values",
            "transactions.csv",
            int(currency_amounts.sum()),
            "Removed currency symbols and converted total_amount to numeric.",
            "The format is inconsistent, but the amount value is usable.",
        )
    )
    df["total_amount"] = (
        df["total_amount"]
        .astype("string")
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")

    duplicate_rows = int(df.duplicated().sum())
    issues.append(
        _issue(
            "Exact duplicate transaction row",
            "transactions.csv",
            duplicate_rows,
            "Dropped exact duplicate rows before warehouse load.",
            "Duplicate transaction IDs and identical values would overstate sales.",
        )
    )
    df = df.drop_duplicates().reset_index(drop=True)

    df["is_guest_customer"] = df["customer_id"].isna()
    issues.append(
        _issue(
            "Missing customer_id",
            "transactions.csv",
            int(df["is_guest_customer"].sum()),
            "Preserved the transaction and flagged it as a guest customer.",
            "Guest transactions are valid sales but should be excluded from customer lifetime spend.",
        )
    )

    df["is_return"] = (df["quantity"] < 0) | (df["total_amount"] < 0)
    issues.append(
        _issue(
            "Return transaction",
            "transactions.csv",
            int(df["is_return"].sum()),
            "Preserved returns as negative fact rows.",
            "Returns reduce net revenue and are required for accurate business reporting.",
        )
    )

    expected_amount = (df["quantity"].astype("float") * df["unit_price"]).round(2)
    df["has_amount_mismatch"] = (expected_amount - df["total_amount"]).abs() > 0.01
    issues.append(
        _issue(
            "Transaction amount differs from quantity times unit_price",
            "transactions.csv",
            int(df["has_amount_mismatch"].sum()),
            "Preserved the source total_amount and flagged the mismatch.",
            "The mismatch may represent discounts or source pricing logic that should not be overwritten.",
        )
    )

    df["has_orphan_store"] = ~df["store_id"].isin(valid_store_ids)
    issues.append(
        _issue(
            "Transaction references unknown store_id",
            "transactions.csv",
            int(df["has_orphan_store"].sum()),
            "Excluded from fact_sales.",
            "The fact table requires a valid store foreign key for trusted warehouse analytics.",
        )
    )

    df["has_orphan_product"] = ~df["product_id"].isin(valid_product_ids)
    issues.append(
        _issue(
            "Transaction references unknown product_id",
            "transactions.csv",
            int(df["has_orphan_product"].sum()),
            "Excluded from fact_sales.",
            "The fact table requires a valid product foreign key for trusted warehouse analytics.",
        )
    )

    df["has_zero_quantity"] = df["quantity"] == 0
    issues.append(
        _issue(
            "Zero quantity transaction",
            "transactions.csv",
            int(df["has_zero_quantity"].sum()),
            "Excluded from fact_sales.",
            "Zero quantity rows do not represent sales or returns and can distort transaction counts.",
        )
    )

    transaction_dates = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["has_future_date"] = transaction_dates.dt.date > as_of_date
    issues.append(
        _issue(
            "Future-dated transaction",
            "transactions.csv",
            int(df["has_future_date"].sum()),
            "Excluded from fact_sales.",
            "Future-dated rows are not part of historical sales reporting as of the processing date.",
        )
    )

    df["has_invalid_date"] = transaction_dates.isna()
    df["has_invalid_amount"] = df["total_amount"].isna() | df["unit_price"].isna() | df["quantity"].isna()
    excluded = (
        df["has_orphan_store"]
        | df["has_orphan_product"]
        | df["has_zero_quantity"]
        | df["has_future_date"]
        | df["has_invalid_date"]
        | df["has_invalid_amount"]
    )

    clean = df.loc[~excluded].copy().reset_index(drop=True)
    clean["customer_id"] = clean["customer_id"].where(clean["customer_id"].notna(), None)
    clean["quantity"] = clean["quantity"].astype(int)
    clean["is_guest_customer"] = clean["is_guest_customer"].astype(bool)
    clean["is_return"] = clean["is_return"].astype(bool)
    clean["has_amount_mismatch"] = clean["has_amount_mismatch"].astype(bool)

    return clean, issues


def clean_all(raw_data: dict[str, pd.DataFrame], as_of_date: date | None = None) -> CleanedData:
    stores, store_issues = clean_stores(raw_data["stores"])
    products, product_issues = clean_products(raw_data["products"])
    transactions, transaction_issues = clean_transactions(
        raw_data["transactions"],
        valid_store_ids=set(stores["store_id"]),
        valid_product_ids=set(products["product_id"]),
        as_of_date=as_of_date,
    )

    return CleanedData(
        stores=stores,
        products=products,
        transactions=transactions,
        data_quality_report=store_issues + product_issues + transaction_issues,
    )
