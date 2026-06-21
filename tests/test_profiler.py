from datetime import date

import pandas as pd

from src.profiler import profile


def test_profile_handles_empty_dataframe() -> None:
    df = pd.DataFrame(columns=["id", "amount"])

    result = profile(df, "empty", as_of_date=date(2026, 6, 20))

    assert result["row_count"] == 0
    assert result["column_count"] == 2
    assert result["duplicate_row_count"] == 0
    assert result["columns"]["id"]["null_percentage"] == 0.0


def test_profile_reports_all_null_column_and_numeric_stats() -> None:
    df = pd.DataFrame({"id": [1, 2, 2], "amount": [0, -5, 10], "notes": [None, None, None]})

    result = profile(df, "sample", as_of_date=date(2026, 6, 20))

    assert result["columns"]["notes"]["null_count"] == 3
    assert result["columns"]["notes"]["null_percentage"] == 100.0
    assert result["columns"]["amount"]["numeric"]["zero_count"] == 1
    assert result["columns"]["amount"]["numeric"]["negative_count"] == 1
