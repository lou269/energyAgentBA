from __future__ import annotations

import pandas as pd


def require_columns(df: pd.DataFrame, columns, name: str) -> None:
    missing = set(columns) - set(df.columns)

    if missing:
        raise ValueError(f"{name} is missing columns: " + ", ".join(sorted(missing)))


def require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value
