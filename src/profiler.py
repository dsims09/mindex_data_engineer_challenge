from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


def parse_mixed_dates(values: pd.Series) -> pd.Series:
    as_string = values.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")

    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"]
    for fmt in formats:
        missing = parsed.isna() & as_string.notna()
        if not missing.any():
            break
        parsed.loc[missing] = pd.to_datetime(as_string.loc[missing], format=fmt, errors="coerce")

    return parsed


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _looks_like_date_column(series: pd.Series, column_name: str) -> bool:
    if "date" in column_name.lower():
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    return False


def profile(df: pd.DataFrame, name: str, as_of_date: date | None = None) -> dict[str, Any]:
    """Return a reusable data quality profile for a DataFrame."""
    as_of_date = as_of_date or date.today()
    row_count = int(len(df))

    report: dict[str, Any] = {
        "name": name,
        "row_count": row_count,
        "column_count": int(len(df.columns)),
        "duplicate_row_count": int(df.duplicated().sum()),
        "columns": {},
    }

    for column in df.columns:
        series = df[column]
        null_count = int(series.isna().sum())
        column_report: dict[str, Any] = {
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_percentage": round((null_count / row_count) * 100, 2) if row_count else 0.0,
        }

        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce")
            column_report["numeric"] = {
                "min": _json_value(numeric.min()),
                "max": _json_value(numeric.max()),
                "mean": _json_value(round(float(numeric.mean()), 4)) if numeric.notna().any() else None,
                "zero_count": int((numeric == 0).sum()),
                "negative_count": int((numeric < 0).sum()),
            }

        if _looks_like_date_column(series, column):
            parsed = parse_mixed_dates(series)
            valid = parsed.dropna()
            column_report["date"] = {
                "min_date": valid.min().date().isoformat() if not valid.empty else None,
                "max_date": valid.max().date().isoformat() if not valid.empty else None,
                "future_date_count": int((valid.dt.date > as_of_date).sum()) if not valid.empty else 0,
                "unparseable_count": int(series.notna().sum() - parsed.notna().sum()),
            }

        report["columns"][column] = column_report

    return report
