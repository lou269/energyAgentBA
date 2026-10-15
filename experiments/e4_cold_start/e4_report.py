# conda activate forecasting-env
# python -m experiments.e4_cold_start.e4_report [run_directory]

import pandas as pd

from docs.plots.plot_e4_cold_start import (
    build_e4_detection_plot,
    build_e4_forecast_plot,
)
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    criteria_table,
    build_setup,
    format_count,
    format_llm,
    format_difference,
    relabel,
    stichtag_labels,
    write_result_report,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.e4_cold_start.e4_config import (
    CLEAN_SCENARIO,
    FORECAST_METRICS_FILE,
    RUN_PREFIX,
    SYSTEM_RESULTS_FILE,
)
from experiments.e4_cold_start.e4_evaluation import E4Summary, summarize_e4
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

SCENARIO_LABELS = {CLEAN_SCENARIO: "Kontrolllauf"} | KIND_LABELS

SETTLING_LABELS = {
    "forecast": "Prognose",
    "notifications": "Meldungen",
    "detection": "Erkennung",
}
NOT_SETTLED = "nicht eingeschwungen"

KEY_HEADERS = {"scenario": "Szenario", "injection_day": "Einbautag"}
VALUE_LABELS = {"scenario": SCENARIO_LABELS}
CHECKED = "✓"
MISSED = "–"


def format_week_count(count: float, total: float) -> str | None:
    # leer, wenn es in dieser Woche nichts zu zählen gab
    if pd.isna(total):
        return None
    return f"{int(count)} von {int(total)}"


def build_criteria_table(
    criteria: pd.DataFrame,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
) -> pd.DataFrame:
    rows = {row["check"]: row for row in criteria.to_dict("records")}
    weeks = rows["weeks_worse_than_longest"]
    resets = rows["extra_resets"]
    detection = rows["detected_share"]
    static = rows["minus_static"]

    return criteria_table(
        [
            (
                f"Tagesfehler bei {shortest} Tagen belastbar höher",
                "0 Wochen",
                format_count(weeks["value"], weeks["total"]),
                weeks["fulfilled"],
            ),
            (
                "zusätzliches Zurücksetzen",
                "0 Läufe",
                format_count(resets["value"], resets["total"]),
                resets["fulfilled"],
            ),
            (
                f"Erkennungsrate, {shortest} bezogen auf {longest} Tage",
                "≥ 90 %",
                format_count(
                    detection["value"], detection["total"], detection["share_pct"]
                ),
                detection["fulfilled"],
            ),
            (
                f"Tagesfehler, {adaptive_model_id} minus {static_model_id}, {shortest} Tage",
                "< 0, belastbar",
                format_difference(
                    static["value"],
                    static["two_se"],
                    bool(static["reliable"]),
                    STANDARD_CONFIG.decimals,
                ),
                static["fulfilled"],
            ),
        ]
    )


def build_study_setup(run_config: dict, run_name: str) -> dict[str, str]:
    e4_config = run_config["e4_config"]
    standard_config = run_config["standard_config"]

    return build_setup(
        run_name,
        standard_config,
        e4_config["cutovers"][standard_config["split"]],
        run_config["code_version"],
        scenarios=f"{', '.join(e4_config['injection_kinds'])}, dazu der Kontrolllauf",
        systems=f"{e4_config['system']} mit Adaption",
        llm=format_llm(
            run_config["system_config"]["llm_config"], "ohne Kalender (CTX0)"
        ),
        details={
            "Einbautage": f"je Lauf ein Einbau an Tag {', '.join(map(str, e4_config['injection_days']))}",
            "Starthistorie": f"{' und '.join(map(str, e4_config['coldstart_days']))} Tage",
            "Auswertung": (
                f"{e4_config['evaluation_days']} Tage ab dem Start in Wochen zu {e4_config['week_days']} Tagen, "
                "je Stichtag dieselben Kalendertage für beide Starthistorien"
            ),
            "Prognosemodelle": (
                f"{run_config['prophet_variant']['model_id']} täglich nachtrainiert, "
                f"{e4_config['static_variant']['model_id']} statisch, nur auf der Starthistorie trainiert"
            ),
        },
    )


def build_totals_table(
    totals: pd.DataFrame,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
) -> pd.DataFrame:
    rows = (
        (f"Tagesfehler {adaptive_model_id} [W]", "day_error_w"),
        (
            f"Tagesfehler {adaptive_model_id} minus {static_model_id} [W]",
            "minus_static_w",
        ),
        (
            "Erkannte Einzelanomalien (erwartete Klasse am Tag nach dem Einbau)",
            "detected",
        ),
        (
            f"Tage im Kontrolllauf, an denen nur bei {shortest} Tagen gemeldet wird",
            "only_shortest",
        ),
        (
            f"Tage im Kontrolllauf, an denen nur bei {longest} Tagen gemeldet wird",
            "only_longest",
        ),
        (
            f"Läufe mit Zurücksetzen nur bei {shortest} Tagen",
            "extra_resets",
        ),
    )

    def cell(measure: str, coldstart_days: int) -> object:
        found = totals.loc[
            totals["measure"].eq(measure) & totals["coldstart_days"].eq(coldstart_days)
        ]
        if found.empty:
            return None
        value, total = found.iloc[0][["value", "total"]]
        return value if pd.isna(total) else format_week_count(value, total)

    return pd.DataFrame(
        {
            "Kennzahl": [label for label, _ in rows],
            f"{shortest} Tage": [cell(measure, shortest) for _, measure in rows],
            f"{longest} Tage": [cell(measure, longest) for _, measure in rows],
        },
        dtype=object,
    )


def build_week_table(
    weeks: pd.DataFrame, *, shortest: int, longest: int
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Woche": weeks["week"].astype("string").fillna("gesamt"),
            "Differenz Tagesfehler [W]": weeks["mean_delta"],
            "belastbar": weeks["exceeds_noise"].map(YES_NO),
            f"Meldung nur bei {shortest}": weeks["only_shortest"].astype("Int64"),
            f"Meldung nur bei {longest}": weeks["only_longest"].astype("Int64"),
            f"erkannt bei {shortest}": [
                format_week_count(count, total)
                for count, total in zip(weeks["detected_shortest"], weeks["injections"])
            ],
            f"erkannt bei {longest}": [
                format_week_count(count, total)
                for count, total in zip(weeks["detected_longest"], weeks["injections"])
            ],
            f"Zurücksetzen nur bei {shortest}": weeks["extra_resets"].astype("Int64"),
        }
    )


def build_settling_table(settling: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Größe": settling["measure"].map(SETTLING_LABELS),
            "ab Woche": settling["settling_week"].map(
                lambda week: NOT_SETTLED if pd.isna(week) else int(week)
            ),
        }
    )


def build_injection_table(
    matrix: pd.DataFrame, stichtage: dict[str, str]
) -> pd.DataFrame:
    keys = matrix[["scenario", "injection_day"]]
    ordered = sorted(
        (column.split("_") for column in matrix.columns[2:]),
        key=lambda run: (run[0], int(run[1])),
    )
    runs = matrix[["_".join(run) for run in ordered]]
    runs.columns = [f"{stichtage[start]}, {days} Tage" for start, days in ordered]

    return pd.concat(
        [
            relabel(keys, KEY_HEADERS, VALUE_LABELS),
            runs.map(lambda detected: CHECKED if detected else MISSED),
        ],
        axis=1,
    )


def build_extra_reset_table(
    extra_resets: pd.DataFrame, stichtage: dict[str, str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Starttermin": extra_resets["start_date"].map(stichtage),
            "Szenario": extra_resets["scenario"].map(SCENARIO_LABELS),
            "Einbautag": extra_resets["injection_day"].astype("Int64"),
            "Zurücksetzen am Tag": extra_resets["day_since_start"],
            "Skala": extra_resets["trigger_scale"],
        }
    ).sort_values(["Starttermin", "Zurücksetzen am Tag"], kind="stable")


def build_tables(
    summary: E4Summary,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
) -> dict[str, tuple[str, pd.DataFrame]]:
    return {
        "result_criteria": (
            "Kriterien der Teilfrage 4",
            build_criteria_table(
                summary.criteria,
                shortest=shortest,
                longest=longest,
                adaptive_model_id=adaptive_model_id,
                static_model_id=static_model_id,
            ),
        ),
        "result_totals": (
            f"Kennzahlen über alle Starttermine, Starthistorie {shortest} gegen {longest} Tage",
            build_totals_table(
                summary.totals,
                shortest=shortest,
                longest=longest,
                adaptive_model_id=adaptive_model_id,
                static_model_id=static_model_id,
            ),
        ),
        "result_weeks": (
            f"Starthistorie {shortest} gegen {longest} Tage je Woche nach dem Start",
            build_week_table(summary.weeks, shortest=shortest, longest=longest),
        ),
        "result_settling": (
            "Einschwingwoche: erste Woche, ab der es keine Abweichung mehr gibt",
            build_settling_table(summary.settling),
        ),
    }


def build_appendix(
    summary: E4Summary,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
    stichtage: dict[str, str],
) -> dict[str, tuple[str, pd.DataFrame]]:
    weeks = summary.forecast.weeks

    return {
        "result_forecast_weeks": (
            f"Tagesfehler {adaptive_model_id} minus {static_model_id} je Woche nach dem Start [W], negativ = {adaptive_model_id} besser",
            pd.DataFrame(
                {
                    "Woche": weeks["week"],
                    f"{shortest} Tage": weeks[f"minus_static_{shortest}"],
                    f"{longest} Tage": weeks[f"minus_static_{longest}"],
                }
            ),
        ),
        "result_extra_resets": (
            f"Zusätzliches Zurücksetzen nur bei {shortest} Tagen, je Lauf",
            build_extra_reset_table(summary.system.extra_resets, stichtage),
        ),
        "result_injections": (
            f"Eingebaute Einzelanomalien: {CHECKED} = erwartete Klasse am Tag nach dem Einbau, {MISSED} = nicht",
            build_injection_table(summary.system.injection_matrix, stichtage),
        ),
    }


def build_notes(shortest: int, longest: int) -> list[str]:
    return [
        "Tag 0 = erster prognostizierter Tag, an ihm wird der letzte Tag der Starthistorie eingeordnet. Ein Einbau an Tag k wird an Tag k + 1 eingeordnet",
        f"Als Meldung zählen die Klassen {', '.join(NOTIFICATION_CLASSIFICATIONS)}. Abweichende Meldungen werden im Kontrolllauf am selben Tag verglichen. Es sind echte Daten, eine Meldung nur bei {shortest} Tagen kann also berechtigt sein",
        f"Erkennungsrate: von den Einzelanomalien, die bei {longest} Tagen am Tag nach dem Einbau mit der erwarteten Klasse eingeordnet werden, der Anteil, den auch {shortest} Tage so einordnen, über alle Tage",
        f"zusätzliches Zurücksetzen: Läufe, in denen bei {shortest} Tagen zurückgesetzt wird und bei {longest} Tagen am selben Tag nicht, je Lauf einmal gezählt",
        "Einschwingwoche: Prognose nach der 2-Standardfehler-Regel, Meldungen nach jedem abweichenden Tag, Erkennung nach jeder Einzelanomalie, die nur die lange Starthistorie erkennt. Die Erkennung ist nur bis zur letzten Woche mit Einbau belegt",
        NOISE_RULE_NOTE,
    ]


def main() -> None:
    run_directory = run_directory_from_argv(PROJECT_CONFIG.e4_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    e4_config = run_config["e4_config"]
    adaptive_model_id = run_config["prophet_variant"]["model_id"]
    static_model_id = e4_config["static_variant"]["model_id"]
    shortest = min(e4_config["coldstart_days"])
    longest = max(e4_config["coldstart_days"])
    stichtage = stichtag_labels(run_config["standard_config"])

    summary = summarize_e4(
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{FORECAST_METRICS_FILE}.csv",
            dtype={"start_date": str},
        ),
        pd.read_csv(
            run_directory / RAW_SUBDIR / f"{SYSTEM_RESULTS_FILE}.csv",
            dtype={"start_date": str},
        ),
        adaptive_model_id=adaptive_model_id,
        static_model_id=static_model_id,
        reference_model_id=run_config["reference_baseline"],
        week_days=e4_config["week_days"],
        smoothing_days=e4_config["smoothing_days"],
    )

    output_directory = user_output_directory(run_directory)
    build_e4_forecast_plot(
        summary.forecast.gap_curve,
        summary.forecast.curve,
        output_directory,
        adaptive_model_id=adaptive_model_id,
        static_model_id=static_model_id,
        shortest=shortest,
        longest=longest,
    )
    build_e4_detection_plot(
        summary.weeks, output_directory, shortest=shortest, longest=longest
    )

    write_result_report(
        output_directory,
        title="E4: Preis einer Adaption",
        setup=build_study_setup(run_config, run_directory.name),
        tables=build_tables(
            summary,
            shortest=shortest,
            longest=longest,
            adaptive_model_id=adaptive_model_id,
            static_model_id=static_model_id,
        ),
        notes=build_notes(shortest, longest)
        + [
            f"Tagesfehler je Tag seit dem Start im Plot: Mittel über die Starttermine, über {e4_config['smoothing_days']} Tage geglättet"
        ],
        images=["e4_forecast.png", "e4_detection.png"],
        decimals=STANDARD_CONFIG.decimals,
        appendix=build_appendix(
            summary,
            shortest=shortest,
            longest=longest,
            adaptive_model_id=adaptive_model_id,
            static_model_id=static_model_id,
            stichtage=stichtage,
        ),
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
