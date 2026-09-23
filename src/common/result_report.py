from pathlib import Path

import pandas as pd

from src.pipeline.io import df_to_csv, write_text_atomic


def format_number(value: str | float | int | None, decimals: int) -> str:
    if pd.isna(value):
        return "-"
    if isinstance(value, float):
        return f"{value:.{decimals}f}".replace(".", ",")
    # LLM-Erklärungen können Zeilenumbrüche und Pipes enthalten, beides zerlegt die Markdown-Tabelle
    return str(value).replace("\n", " ").replace("|", "/")


def markdown_table(table: pd.DataFrame, decimals: int) -> str:
    header = "| " + " | ".join(table.columns) + " |"
    divider = "|" + "|".join("---:" if pd.api.types.is_numeric_dtype(table[column]) else "---" for column in table.columns) + "|"
    rows = ["| " + " | ".join(format_number(value, decimals) for value in row) + " |" for row in table.itertuples(index=False)]

    return "\n".join([header, divider, *rows])


def write_result_report(
    output_directory: Path,
    *,
    title: str,
    setup: dict[str, str],
    tables: dict[str, tuple[str, pd.DataFrame]],
    notes: list[str],
    images: list[str],
    decimals: int,
) -> None:
    """ergebnis.md plus je Tabelle eine gerundete CSV, tables bildet Dateiname auf (Überschrift, Tabelle) ab"""
    lines = [f"# {title}", "", "## Setup", ""]
    lines += [f"- {key}: {value}" for key, value in setup.items()]

    for filename, (heading, table) in tables.items():
        df_to_csv(table.round(decimals), output_directory, filename)
        lines += ["", f"## {heading}", "", markdown_table(table, decimals)]

    if notes:
        lines += ["", "## Hinweise", ""]
        lines += [f"- {note}" for note in notes]

    for image in images:
        lines += ["", f"![{image}]({image})"]

    write_text_atomic("\n".join(lines) + "\n", output_directory / "ergebnis.md")
