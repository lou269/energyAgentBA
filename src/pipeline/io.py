from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pandas as pd


def df_to_csv(df: pd.DataFrame, output_path: Path, filename: str) -> None:
    output_file = output_path / f"{filename}.csv"
    df.to_csv(output_file, index=False)

def save_json(
    data: dict[str, Any],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = output_file.with_suffix(output_file.suffix + ".tmp")

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