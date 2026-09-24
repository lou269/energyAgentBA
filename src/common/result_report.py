from pathlib import Path
from typing import Any

import pandas as pd

from src.pipeline.io import df_to_csv, write_text_atomic


def format_number(value: Any, decimals: int) -> str:
    if pd.isna(value):
        return "-"
    if isinstance(value, float):
        return f"{value:.{decimals}f}".replace(".", ",")
    # LLM-Erklärungen können Zeilenumbrüche und Pipes enthalten, beides zerlegt die Markdown-Tabelle
    return str(value).replace("\n", " ").replace("|", "/")


def key_figures_table(rows: list[tuple[str, object, str]]) -> pd.DataFrame:
    # je Lauf dieselben drei Spalten, damit sich die Kernzahlen aller K und E später zusammenlegen lassen object, sonst werden Tage und Zählungen zu 13,0
    return pd.DataFrame(rows, columns=["Kennzahl", "Wert", "Bezug"], dtype=object)


def format_commit(code_version: dict) -> str:
    return code_version["git_commit"][:7] + (
        " (mit lokalen Änderungen)" if code_version["git_dirty"] else ""
    )


def markdown_table(table: pd.DataFrame, decimals: int) -> str:
    header = "| " + " | ".join(table.columns) + " |"
    divider = (
        "|"
        + "|".join(
            "---:" if pd.api.types.is_numeric_dtype(table[column]) else "---"
            for column in table.columns
        )
        + "|"
    )
    rows = [
        "| " + " | ".join(format_number(value, decimals) for value in row) + " |"
        for row in table.itertuples(index=False)
    ]

    return "\n".join([header, divider, *rows])


def _rounded(table: pd.DataFrame, decimals: int) -> pd.DataFrame:
    # round() lässt object-Spalten aus, in den Kennzahlen stehen Zahlen aber neben Text
    return table.map(
        lambda value: round(value, decimals) if isinstance(value, float) else value
    )


def write_result_report(
    output_directory: Path,
    *,
    title: str,
    setup: dict[str, str],
    tables: dict[str, tuple[str, pd.DataFrame]],
    notes: list[str],
    images: list[str],
    decimals: int,
    appendix: dict[str, tuple[str, pd.DataFrame]] | None = None,
) -> None:
    """ergebnis.md plus je Tabelle eine gerundete CSV, tables/appendix bilden Dateiname auf (Überschrift, Tabelle) ab"""
    lines = [f"# {title}", "", "## Setup", ""]
    lines += [f"- {key}: {value}" for key, value in setup.items()]

    for filename, (heading, table) in tables.items():
        df_to_csv(_rounded(table, decimals), output_directory, filename)
        lines += ["", f"## {heading}", "", markdown_table(table, decimals)]

    if notes:
        lines += ["", "## Hinweise", ""]
        lines += [f"- {note}" for note in notes]

    for image in images:
        lines += ["", f"![{image}]({image})"]

    if appendix:
        lines += ["", "## Anhang"]
        for filename, (heading, table) in appendix.items():
            df_to_csv(_rounded(table, decimals), output_directory, filename)
            lines += ["", f"### {heading}", "", markdown_table(table, decimals)]

    write_text_atomic("\n".join(lines) + "\n", output_directory / "ergebnis.md")
