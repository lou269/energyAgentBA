from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.project_config import ProjectConfig


def read_canonical_frame(project_config: ProjectConfig, name: str) -> pd.DataFrame:
    return pd.read_csv(
        project_config.canonical_output_dir / f"{name}.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )


def read_target_meter_key(project_config: ProjectConfig) -> str:
    canonical_manifest = pd.read_csv(project_config.canonical_output_dir / "canonical_manifest.csv")

    if len(canonical_manifest) != 1:
        raise ValueError("Canonical manifest must contain exactly one mains target.")

    return str(canonical_manifest.iloc[0]["meter_key"])


def df_to_csv(df: pd.DataFrame, output_path: Path, filename: str) -> None:
    output_file = output_path / f"{filename}.csv"
    df.to_csv(output_file, index=False)


def append_csv(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, mode="a", header=not output_file.exists(), index=False)


def append_jsonl(record: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
        file.write("\n")


def latest_sequential_number(directory: Path, prefix: str) -> int | None:
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")

    numbers = [
        int(match.group(1))
        for entry in (directory.iterdir() if directory.exists() else ())
        if entry.is_dir() and (match := pattern.match(entry.name))
    ]

    return max(numbers, default=None)


def next_sequential_number(directory: Path, prefix: str) -> int:
    return (latest_sequential_number(directory, prefix) or 0) + 1


def find_run_directory(directory: Path, prefix: str, number: int | None = None) -> tuple[int, Path] | None:
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)(?:_.*)?$")

    candidates = [
        (int(match.group(1)), entry)
        for entry in (directory.iterdir() if directory.exists() else ())
        if entry.is_dir() and (match := pattern.match(entry.name))
    ]

    if number is not None:
        candidates = [candidate for candidate in candidates if candidate[0] == number]

    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate[0])


def write_text_atomic(content: str, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = output_file.with_suffix(output_file.suffix + ".tmp")

    try:
        temporary_file.write_text(content, encoding="utf-8")
        temporary_file.replace(output_file)
    finally:
        temporary_file.unlink(missing_ok=True)


def save_json(
    data: dict[str, Any],
    output_file: Path,
) -> None:
    write_text_atomic(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ),
        output_file,
    )