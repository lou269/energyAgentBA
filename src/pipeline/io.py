from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pandas as pd


def df_to_csv(df: pd.DataFrame, output_path: Path, filename: str) -> None:
    output_file = output_path / f"{filename}.csv"
    df.to_csv(output_file, index=False)


def load_or_build_csv(
    output_path: Path,
    filename: str,
    build: Callable[[], pd.DataFrame],
    overwrite: bool = False,
) -> pd.DataFrame:
    output_file = output_path / f"{filename}.csv"

    if output_file.exists() and not overwrite:
        return pd.read_csv(output_file)

    dataframe = build()
    df_to_csv(dataframe, output_path, filename)
    return dataframe


def load_or_build_csv_pair(
    output_path: Path,
    first_filename: str,
    second_filename: str,
    build: Callable[[], tuple[pd.DataFrame, pd.DataFrame]],
    overwrite: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    first_file = output_path / f"{first_filename}.csv"
    second_file = output_path / f"{second_filename}.csv"

    if first_file.exists() and second_file.exists() and not overwrite:
        return pd.read_csv(first_file), pd.read_csv(second_file)

    first_dataframe, second_dataframe = build()
    df_to_csv(first_dataframe, output_path, first_filename)
    df_to_csv(second_dataframe, output_path, second_filename)

    return first_dataframe, second_dataframe

def save_json(
    data: dict[str, Any],
    output_file: Path,
) -> None:
    """Save JSON atomically."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = output_file.with_suffix(
        output_file.suffix + ".tmp"
    )

    try:
        temporary_file.write_text(
            json.dumps(
                data,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary_file.replace(output_file)
    finally:
        temporary_file.unlink(missing_ok=True)