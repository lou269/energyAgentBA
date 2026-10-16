from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from src.pipeline.io import df_to_csv, write_text_atomic


def split_cutover_dates(standard_config: Mapping[str, Any]) -> Mapping[str, str]:
    # aus der run_config: die Termine des Abschnitts, auf dem der Lauf war
    return standard_config["cutover_dates"][standard_config["split"]]


def stichtag_labels(standard_config: Mapping[str, Any]) -> dict[str, str]:
    dates = sorted(
        date
        for split_dates in standard_config["cutover_dates"].values()
        for date in split_dates.values()
    )
    return {date: f"SF{number}" for number, date in enumerate(dates, start=1)}


def format_cutovers(
    standard_config: Mapping[str, Any], cutover_ids: Sequence[str]
) -> str:
    cutover_dates = split_cutover_dates(standard_config)
    labels = stichtag_labels(standard_config)
    return ", ".join(
        f"{labels[date]}: {pd.Timestamp(date):%d.%m.%Y}"
        for date in sorted(cutover_dates[cutover] for cutover in cutover_ids)
    )


KIND_LABELS: dict[str, str] = {"control": "Kontrolllauf"} | {
    kind: kind
    for kind in (
        "scaled",
        "scaled_strong",
        "scaled_down",
        "scaled_down_strong",
        "ramp_28",
        "ramp_28_strong",
        "ramp_28_down",
        "ramp_28_down_strong",
        "ramp_56",
        "ramp_56_down",
        "peak",
        "peak_strong",
        "level",
        "stuck",
    )
}


# Sollverhalten des Vorfilters (EXPECTED_DETECTION)
DETECTION_LABELS: dict[str, str] = {
    "reset": "erkennen (Zurücksetzen)",
    "alarm": "Einzelanomalie am Ereignistag",
    "silent": "still bleiben",
    "flag": "als Messfehler markieren",
}

YES_NO = {True: "ja", False: "nein"}
NOISE_RULE_NOTE = "belastbar: Betrag der Differenz größer als 2 Standardfehler der gepaarten Differenzen, grobe Faustregel"
CRITERIA_COLUMNS = ["Kriterium", "Ziel", "Ergebnis", "erfüllt"]


def format_count(count: Any, total: Any, share_pct: Any = None) -> str:
    text = f"{int(count)} von {int(total)}"
    if share_pct is None or pd.isna(share_pct):
        return text
    digits = 1 if share_pct < 10 else 0
    return f"{text} ({share_pct:.{digits}f} %)".replace(".", ",")


def format_watts(value: Any, decimals: int) -> str:
    return f"{format_number(float(value), decimals)} W".replace("-", "−")


def format_difference(
    value: Any, two_standard_errors: Any, reliable: Any, decimals: int
) -> str:
    return (
        f"{format_watts(value, decimals)}, 2 Standardfehler "
        f"{format_watts(two_standard_errors, decimals)}, "
        f"{'belastbar' if reliable else 'nicht belastbar'}"
    )


def criteria_table(rows: list[tuple[str, str, str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            (label, target, result, YES_NO[bool(met)])
            for label, target, result, met in rows
        ],
        columns=CRITERIA_COLUMNS,
        dtype=object,
    )


def format_number(value: Any, decimals: int) -> str:
    if pd.isna(value):
        return "-"
    if isinstance(value, float):
        return f"{value:.{decimals}f}".replace(".", ",").replace("-", "−")
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


def format_llm(llm_config: Mapping[str, Any], calendar: str) -> str:
    return f"{llm_config['model']}, Prompt {llm_config['prompt_version']}, {calendar}"


def build_setup(
    run_name: str,
    standard_config: Mapping[str, Any],
    cutover_ids: Sequence[str] | None,
    code_version: Mapping[str, Any],
    *,
    scenarios: str | None = None,
    systems: str | None = None,
    llm: str | None = None,
    details: Mapping[str, str] | None = None,
) -> dict[str, str]:
    setup = {"Lauf": run_name}
    if cutover_ids is not None:
        setup["Stichtage"] = format_cutovers(standard_config, cutover_ids)
    for key, value in (
        ("Szenarien", scenarios),
        ("Systeme", systems),
        ("Sprachmodell", llm),
    ):
        if value is not None:
            setup[key] = value

    return setup | dict(details or {}) | {"Commit": format_commit(code_version)}  # type: ignore


def format_difference_range(value: Any, two_standard_errors: Any, decimals: int) -> str:
    return f"{format_number(float(value), decimals)} (± {format_number(float(two_standard_errors), decimals)})"


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


LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_\allowbreak{}",
    "{": r"\{",
    "}": r"\}",
    "^": r"\textasciicircum{}",
    "−": r"\textminus{}",
    "×": r"\texttimes{}",
    "≥": r"$\geq$",
    "✓": r"$\checkmark$",
}


WIDE_TABLE_COLUMNS = 7


def _latex_cell(value: Any, decimals: int) -> str:
    text = format_number(value, decimals)
    escaped = "".join(LATEX_ESCAPES.get(char, char) for char in text)
    if isinstance(value, float) and len(escaped) > 1:
        escaped = escaped.replace("-", "$-$")

    return escaped


def latex_table(table: pd.DataFrame, decimals: int) -> str:
    alignment = " ".join(
        "R" if pd.api.types.is_numeric_dtype(table[column]) else "T"
        for column in table.columns
    )
    header = " & ".join(_latex_cell(str(column), decimals) for column in table.columns)
    rows = [
        " & ".join(_latex_cell(value, decimals) for value in row) + r" \\"
        for row in table.itertuples(index=False)
    ]
    start = [rf"\begin{{tabzahlen}}{{{alignment}}}", header + r" \\", r"\midrule"]

    return "\n".join(start + rows + [r"\end{tabzahlen}"])


def latex_escape(text: str) -> str:
    return "".join(LATEX_ESCAPES.get(char, char) for char in text)


def latex_long_table(table: pd.DataFrame, decimals: int) -> str:
    demand = [
        max(
            round(1.3 * max(len(word) for word in str(column).split())),
            min(
                max(
                    (len(format_number(value, decimals)) for value in table[column]),
                    default=1,
                ),
                40,
            ),
            3,
        )
        + 2
        for column in table.columns
    ]
    scale = len(demand) / sum(demand)
    alignment = " ".join(
        ("V" if pd.api.types.is_numeric_dtype(table[column]) else "W")
        + f"{{{width * scale:.2f}}}"
        for column, width in zip(table.columns, demand)
    )
    header = " & ".join(_latex_cell(str(column), decimals) for column in table.columns)
    rows = [
        " & ".join(_latex_cell(value, decimals) for value in row) + r" \\"
        for row in table.itertuples(index=False)
    ]
    size = (
        r"[\small\setlength{\tabcolsep}{3pt}]"
        if len(demand) > WIDE_TABLE_COLUMNS
        else r"[\small]"
    )

    return "\n".join(
        [rf"\begin{{tablang}}{size}{{{alignment}}}{{{header}}}"]
        + rows
        + [r"\end{tablang}"]
    )


def _latex_table_block(
    level: str, heading: str, table: pd.DataFrame, decimals: int
) -> list[str]:
    block = [
        rf"\{level}*{{{latex_escape(heading)}}}",
        latex_long_table(table, decimals),
    ]
    if len(table.columns) > WIDE_TABLE_COLUMNS:
        block = [r"\begin{landscape}"] + block + [r"\end{landscape}"]

    return [""] + block


def _latex_figure(image: str) -> list[str]:
    return [
        r"\begin{center}",
        rf"\includegraphics[width=\linewidth]{{{Path(image).with_suffix('.pdf').name}}}",
        r"\end{center}",
    ]


def _latex_items(items: list[str]) -> list[str]:
    return (
        [r"\begin{itemize}"] + [rf"\item {item}" for item in items] + [r"\end{itemize}"]
    )


def _markdown_lines_to_latex(text_lines: list[str]) -> list[str]:
    latex: list[str] = []
    items: list[str] = []
    for line in text_lines + [""]:
        if line.startswith("- "):
            items.append(latex_escape(line[2:]))
            continue
        if items:
            latex += _latex_items(items)
            items = []
        if line.startswith("!["):
            latex += _latex_figure(line[line.index("(") + 1 : line.rindex(")")])
        elif line.startswith("**") and line.endswith("**"):
            latex += ["", rf"\paragraph{{{latex_escape(line.strip('*'))}}}"]
        elif line:
            latex.append(latex_escape(line))

    return latex


def _report_label(title: str) -> str:
    return "app:report_" + title.split(":")[0].strip().lower().replace(" ", "_")


def _save_table(
    output_directory: Path, filename: str, table: pd.DataFrame, decimals: int
) -> None:
    # CSV und LaTeX-Tabelle zum Einbinden mit \input, ergebnis.md baut die Markdown-Tabelle selbst
    df_to_csv(_rounded(table, decimals), output_directory, filename)
    write_text_atomic(
        latex_table(table, decimals) + "\n", output_directory / f"{filename}.tex"
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
    lines = [f"# {title}"]
    tex = [rf"\section{{{latex_escape(title)}}}", rf"\label{{{_report_label(title)}}}"]
    if summary:
        lines += ["", "## Kurzfassung", ""] + [f"- {line}" for line in summary]
        tex += [r"\subsection*{Kurzfassung}"] + _latex_items(
            [latex_escape(line) for line in summary]
        )
    lines += ["", "## Setup", ""]
    lines += [f"- {key}: {value}" for key, value in setup.items()]
    tex += [r"\subsection*{Setup}"] + _latex_items(
        [
            rf"\textbf{{{latex_escape(key)}:}} {latex_escape(value)}"
            for key, value in setup.items()
        ]
    )

    for filename, (heading, table) in tables.items():
        _save_table(output_directory, filename, table, decimals)
        lines += ["", f"## {heading}", "", markdown_table(table, decimals)]
        tex += _latex_table_block("subsection", heading, table, decimals)

    if notes:
        lines += ["", "## Hinweise", ""]
        lines += [f"- {note}" for note in notes]
        tex += ["", r"\subsection*{Hinweise}"] + _latex_items(
            [latex_escape(note) for note in notes]
        )

    for image in images:
        lines += ["", f"![{image}]({image})"]
        tex += _latex_figure(image)

    if appendix or appendix_text:
        lines += ["", "## Anhang"]
        tex += ["", r"\subsection*{Weitere Tabellen}"]
        for filename, (heading, table) in (appendix or {}).items():
            _save_table(output_directory, filename, table, decimals)
            lines += ["", f"### {heading}", "", markdown_table(table, decimals)]
            tex += _latex_table_block("subsubsection", heading, table, decimals)
        for heading, text_lines in appendix_text or []:
            lines += ["", f"### {heading}", ""] + text_lines
            tex += [
                "",
                rf"\subsubsection*{{{latex_escape(heading)}}}",
            ] + _markdown_lines_to_latex(text_lines)

    write_text_atomic("\n".join(lines) + "\n", output_directory / "ergebnis.md")
    write_text_atomic("\n".join(tex) + "\n", output_directory / "ergebnis.tex")


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


def forecast_error_table(
    errors: pd.DataFrame, unit: str, reference: str
) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Tagesfehler [W]": errors["mean_day_error_w"],
            "MAE [W]": errors["mean_mae_w"],
        }
    ).join(paired_difference_columns(errors, unit))
    table.insert(3, f"Differenz MAE gegen {reference} [W]", errors["mae_delta_w"])

    return table.rename(
        columns={"Differenz [W]": f"Differenz Tagesfehler gegen {reference} [W]"}
    )
