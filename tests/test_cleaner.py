from datetime import date

import pandas as pd

from src.cleaner import clean_products, clean_stores, clean_transactions


def test_clean_stores_standardizes_zip_region_and_duplicate_store() -> None:
    stores = pd.DataFrame(
        [
            {
                "store_id": "S001",
                "store_name": "First Name",
                "city": "Rochester",
                "state": "NY",
                "zip_code": "0938",
                "region": None,
                "opened_date": "2020-01-01",
            },
            {
                "store_id": "S001",
                "store_name": "Second Name",
                "city": "Rochester",
                "state": "NY",
                "zip_code": "0938",
                "region": "Northeast",
                "opened_date": "2020-01-01",
            },
        ]
    )

    cleaned, issues = clean_stores(stores)

    assert len(cleaned) == 1
    assert cleaned.loc[0, "zip_code"] == "00938"
    assert cleaned.loc[0, "region"] == "Unknown"
    assert any(issue["issue"] == "Duplicate store_id with conflicting name" for issue in issues)


def test_clean_products_flags_catalog_conflicts_and_zero_price() -> None:
    products = pd.DataFrame(
        [
            {"product_id": "P001", "product_name": "Widget", "category": None, "unit_price": 10.0, "supplier_id": "SUP001"},
            {"product_id": "P001", "product_name": "Widget", "category": None, "unit_price": 12.0, "supplier_id": "SUP001"},
            {"product_id": "P002", "product_name": "Freebie", "category": "Office", "unit_price": 0.0, "supplier_id": "SUP002"},
        ]
    )

    cleaned, _ = clean_products(products)

    p001 = cleaned.loc[cleaned["product_id"] == "P001"].iloc[0]
    p002 = cleaned.loc[cleaned["product_id"] == "P002"].iloc[0]
    assert p001["category"] == "Uncategorized"
    assert p001["catalog_unit_price"] == 12.0
    assert bool(p001["has_catalog_price_conflict"]) is True
    assert bool(p002["has_zero_catalog_price"]) is True


def test_clean_transactions_excludes_invalid_facts_and_preserves_returns() -> None:
    transactions = pd.DataFrame(
        [
            {
                "transaction_id": "T001",
                "transaction_date": "06/01/2026",
                "store_id": "S001",
                "product_id": "P001",
                "customer_id": None,
                "quantity": 2,
                "unit_price": 5.0,
                "total_amount": "$10.00",
            },
            {
                "transaction_id": "T002",
                "transaction_date": "2026-06-01",
                "store_id": "S999",
                "product_id": "P001",
                "customer_id": "C001",
                "quantity": 1,
                "unit_price": 5.0,
                "total_amount": 5.0,
            },
            {
                "transaction_id": "T003",
                "transaction_date": "2026-06-01",
                "store_id": "S001",
                "product_id": "P001",
                "customer_id": "C002",
                "quantity": -1,
                "unit_price": 5.0,
                "total_amount": -5.0,
            },
        ]
    )

    cleaned, _ = clean_transactions(
        transactions,
        valid_store_ids={"S001"},
        valid_product_ids={"P001"},
        as_of_date=date(2026, 6, 20),
    )

    assert set(cleaned["transaction_id"]) == {"T001", "T003"}
    assert bool(cleaned.loc[cleaned["transaction_id"] == "T001", "is_guest_customer"].iloc[0]) is True
    assert bool(cleaned.loc[cleaned["transaction_id"] == "T003", "is_return"].iloc[0]) is True
