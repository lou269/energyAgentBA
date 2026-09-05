from __future__ import annotations

import pandas as pd


MERGE_KEYS = ["house", "meter_instance", "meter_key"]


def require_columns(df: pd.DataFrame, columns, name: str) -> None:
    missing = set(columns) - set(df.columns)

    if missing:
        raise ValueError(f"{name} is missing columns: " + ", ".join(sorted(missing)))
