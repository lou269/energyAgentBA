from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from experiments.common.standard_config import STANDARD_CONFIG
from src.pipeline.io import df_to_csv, write_text_atomic


def format_cutovers(
    cutover_dates: Mapping[str, str], cutover_ids: Sequence[str]
) -> str:
    return ", ".join(
        f"{cutover_id} ({cutover_dates[cutover_id]})" for cutover_id in cutover_ids
    )


def _change_label(prefix: str, factor: float) -> str:
    # ×1,2 als +20 %, ×0,8 als −20 %
    return f"{prefix} {(factor - 1) * 100:+.0f} %".replace("-", "−")


# Beschriftung der Katalog-Arten in den Reports, Stärken aus STANDARD_CONFIG
KIND_LABELS: dict[str, str] = {
    "control": "keine Änderung",
    "scaled": _change_label("Sprung", STANDARD_CONFIG.scale_factor),
    "scaled_strong": _change_label("Sprung", STANDARD_CONFIG.strong_scale_factor),
    "ramp_28": _change_label(
        f"Rampe über {STANDARD_CONFIG.ramp_fast_days} Tage",
        STANDARD_CONFIG.scale_factor,
    ),
    "ramp_28_down": _change_label(
        f"Rampe über {STANDARD_CONFIG.ramp_fast_days} Tage",
        STANDARD_CONFIG.scale_factor_down,
    ),
    "ramp_56": _change_label(
        f"Rampe über {STANDARD_CONFIG.ramp_slow_days} Tage",
        STANDARD_CONFIG.scale_factor,
    ),
    "ramp_56_down": _change_label(
        f"Rampe über {STANDARD_CONFIG.ramp_slow_days} Tage",
        STANDARD_CONFIG.scale_factor_down,
    ),
    "peak": f"Spitze +{STANDARD_CONFIG.peak_extra_w:g} W über {STANDARD_CONFIG.peak_hours} h",
    "peak_strong": f"Spitze +{STANDARD_CONFIG.strong_peak_extra_w:g} W über {STANDARD_CONFIG.peak_hours} h",
    "level": f"ganzer Tag +{STANDARD_CONFIG.level_extra_w:g} W",
    "stuck": f"Festhänger über {STANDARD_CONFIG.stuck_hours} h",
}

# Sollverhalten des Vorfilters (EXPECTED_DETECTION)
DETECTION_LABELS: dict[str, str] = {
    "reset": "erkennen (Reset)",
    "alarm": "Alarm am Ereignistag",
    "silent": "still bleiben",
    "flag": "als Messfehler markieren",
}

# Vorlage für die Erklärungsbewertung, Texte aus E2 und E5
EXPLANATION_RATING_FILE = "explanation_ratings_template"
YES_NO = {True: "ja", False: "nein"}
NOISE_RULE_NOTE = "belastbar: Betrag der Differenz größer als 2 Standardfehler der gepaarten Differenzen, grobe Faustregel"


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


def relabel(
    table: pd.DataFrame,
    headers: dict[str, str],
    value_labels: dict[str, dict] | None = None,
) -> pd.DataFrame:
    # value_labels: Spalte -> {Wert: lesbarer Text}, danach die Spaltenköpfe
    labeled = table.copy()
    for column, labels in (value_labels or {}).items():
        if column in labeled:
            labeled[column] = labeled[column].map(labels)

    return labeled.rename(columns=headers)


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

    return "\n".join([header, divider] + rows)


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
    appendix_text: list[tuple[str, list[str]]] | None = None,
    summary: list[str] | None = None,
) -> None:
    # ergebnis.md plus je Tabelle eine gerundete CSV, tables/appendix bilden Dateiname auf (Überschrift, Tabelle) ab
    lines = [f"# {title}"]
    if summary:
        lines += ["", "## Kurzfassung", ""] + [f"- {line}" for line in summary]
    lines += ["", "## Setup", ""]
    lines += [f"- {key}: {value}" for key, value in setup.items()]

    for filename, (heading, table) in tables.items():
        df_to_csv(_rounded(table, decimals), output_directory, filename)
        lines += ["", f"## {heading}", "", markdown_table(table, decimals)]

    if notes:
        lines += ["", "## Hinweise", ""]
        lines += [f"- {note}" for note in notes]

    for image in images:
        lines += ["", f"![{image}]({image})"]

    if appendix or appendix_text:
        lines += ["", "## Anhang"]
        for filename, (heading, table) in (appendix or {}).items():
            df_to_csv(_rounded(table, decimals), output_directory, filename)
            lines += ["", f"### {heading}", "", markdown_table(table, decimals)]
        for heading, text_lines in appendix_text or []:
            lines += ["", f"### {heading}", ""] + text_lines

    write_text_atomic("\n".join(lines) + "\n", output_directory / "ergebnis.md")


def answer_bullets(
    explanation: str, recommendation: str, uncertainty: str
) -> list[str]:
    return [
        f"- Erklärung: {explanation}",
        f"- Empfehlung: {recommendation}",
        f"- Unsicherheit: {uncertainty}",
    ]


def paired_difference_columns(paired: pd.DataFrame, unit: str) -> pd.DataFrame:
    # Lesbare Spalten zu summarize_paired_differences, unit sagt, was gepaart wurde (Tage, Origins)
    return pd.DataFrame(
        {
            "Differenz [W]": paired["mean_delta"],
            "2 Standardfehler [W]": 2 * paired["delta_standard_error"],
            unit: paired["paired_count"].astype("Int64"),
            f"{unit} besser [%]": paired["better_share"] * 100,
            "belastbar": paired["exceeds_noise"].map(YES_NO),
        }
    )


def write_explanation_rating_template(
    llm_outputs: pd.DataFrame, output_directory: Path
) -> None:
    # rubric_score füllen die Bewertenden aus
    df_to_csv(
        llm_outputs.assign(rubric_score=""), output_directory, EXPLANATION_RATING_FILE
    )
