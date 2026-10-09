# conda activate forecasting-env
# python -m experiments.e4_cold_start.e4_report [run_directory]

import pandas as pd

from docs.plots.plot_e4_cold_start import build_e4_forecast_plot
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    format_commit,
    format_cutovers,
    format_number,
    relabel,
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
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

SCENARIO_LABELS = {CLEAN_SCENARIO: "ohne Injektion"} | KIND_LABELS

CRITERION_LABELS = {
    "forecast": "Prognose",
    "no_malfunction": "keine Fehlfunktion",
    "detection": "Erkennung",
}

CHECK_LABELS = {
    "weeks_worse_than_longest": "Wochen, in denen der Tagesfehler belastbar über dem des langen Kaltstarts liegt",
    "first_week_minus_reference_w": "Tagesfehler gegenüber der Baseline in Woche 1 [W], höchstens 0",
    "extra_resets_before_all_scales": "Resets nur beim kurzen Kaltstart, solange nicht alle Skalen einen Score haben",
    "missed_after_weekday": "Injektionen ab dem Tag mit weekday, die nur der lange Kaltstart erkennt",
}

SETTLING_LABELS = {
    "forecast": "Prognose",
    "notifications": "Meldungen",
    "detection": "Erkennung",
}
NOT_SETTLED = "nicht eingeschwungen"

KEY_HEADERS = {"scenario": "Szenario", "injection_day": "Injektionstag"}
VALUE_LABELS = {"scenario": SCENARIO_LABELS}
CHECKED = "✓"
MISSED = "–"


def format_count(count: float, total: float) -> str | None:
    # leer, wenn es in dieser Woche nichts zu zählen gab
    if pd.isna(total):
        return None
    return f"{int(count)} von {int(total)}"


def build_criteria_table(criteria: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Bedingung": criteria["criterion"].map(CRITERION_LABELS),
            "Prüfung": criteria["check"].map(CHECK_LABELS),
            "erfüllt": criteria["fulfilled"].map(YES_NO),
            "Wert": criteria["value"],
        }
    )


def build_setup(run_config: dict) -> dict[str, str]:
    e4_config = run_config["e4_config"]
    standard_config = run_config["standard_config"]
    system_config = run_config["system_config"]
    llm_config = system_config["llm_config"]

    return {
        "Starttermine": (
            f"Standard-Cutover {format_cutovers(standard_config, e4_config['cutovers'][standard_config['split']])} "
            f"({standard_config['split']})"
        ),
        "Kaltstart": (
            f"{', '.join(map(str, e4_config['coldstart_days']))} Tage, "
            "jeweils alle Tage am ersten Entscheidungstag, der erste eingeordnete Tag zählt mit"
        ),
        "Auswertung": (
            f"{e4_config['evaluation_days']} Tage ab Start in Wochen zu {e4_config['week_days']} Tagen, "
            "je Starttermin dieselben Kalendertage für alle Kaltstart-Längen"
        ),
        "Prognose (E4a)": (
            f"{run_config['prophet_variant']['model_id']} täglich nachtrainiert, "
            f"{e4_config['static_variant']['model_id']} nur auf den Starttagen, "
            f"Baseline {run_config['reference_baseline']}, Seed {run_config['seed']}"
        ),
        "Kreislauf (E4b)": (
            f"{SYS_LABELS[e4_config['system']]}, {llm_config['model']}, Prompt {llm_config['prompt_version']}, "
            f"Temperatur {llm_config['temperature']:g}, Adaption an"
        ),
        "Injektionen": (
            f"{', '.join(SCENARIO_LABELS[kind] for kind in e4_config['injection_kinds'])}, "
            f"je Lauf eine, an Tag {', '.join(map(str, e4_config['injection_days']))}, eingeordnet am Tag danach"
        ),
        "Commit": format_commit(run_config["code_version"]),
    }


def build_totals_table(
    totals: pd.DataFrame,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
) -> pd.DataFrame:
    rows = (
        ("Prognosefehler gesamt [W]", "day_error_w"),
        (
            f"Prognosefehler gegenüber {static_model_id} [W], negativ = besser",
            "minus_static_w",
        ),
        (
            f"Prognosefehler gegenüber {reference_model_id} [W], negativ = besser",
            "minus_reference_w",
        ),
        (
            "Falschmeldungen: Tage, an denen nur der kurze Kaltstart meldet",
            "only_shortest",
        ),
        (
            "Verpasste Meldungen: Tage, an denen nur der lange Kaltstart meldet",
            "only_longest",
        ),
        (
            "Anomalie erkannt: eingebaute Injektionen mit der erwarteten Klasse",
            "detected",
        ),
        (
            "Falsche new_pattern: Läufe mit Reset nur beim kurzen Kaltstart",
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
        return value if pd.isna(total) else format_count(value, total)

    return pd.DataFrame(
        {
            "Kennzahl": [label for label, _ in rows],
            f"{adaptive_model_id}, Kaltstart {shortest} Tage": [
                cell(measure, shortest) for _, measure in rows
            ],
            f"{adaptive_model_id}, Kaltstart {longest} Tage (Referenz)": [
                cell(measure, longest) for _, measure in rows
            ],
        },
        dtype=object,
    )


def build_week_table(
    weeks: pd.DataFrame, *, shortest: int, longest: int, adaptive_model_id: str
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Woche": weeks["week"].astype("string").fillna("gesamt"),
            f"Prognose {adaptive_model_id}: {shortest} minus {longest} Tage [W]": weeks[
                "mean_delta"
            ],
            "belastbar": weeks["exceeds_noise"].map(YES_NO),
            f"Falschmeldungen (nur bei {shortest} Tagen gemeldet)": weeks[
                "only_shortest"
            ].astype("Int64"),
            f"Verpasste Meldungen (nur bei {longest} Tagen gemeldet)": weeks[
                "only_longest"
            ].astype("Int64"),
            f"Anomalie erkannt, {shortest} Tage": [
                format_count(count, total)
                for count, total in zip(weeks["detected_shortest"], weeks["injections"])
            ],
            f"Anomalie erkannt, {longest} Tage": [
                format_count(count, total)
                for count, total in zip(weeks["detected_longest"], weeks["injections"])
            ],
            f"falsche new_pattern (nur bei {shortest} Tagen)": weeks[
                "extra_resets"
            ].astype("Int64"),
        }
    )


def build_settling_table(settling: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Größe": settling["measure"].map(SETTLING_LABELS),
            "eingeschwungen ab Woche": settling["settling_week"].map(
                lambda week: NOT_SETTLED if pd.isna(week) else int(week)
            ),
        }
    )


def build_tables(
    summary: E4Summary,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
) -> dict[str, tuple[str, pd.DataFrame]]:
    return {
        "result_criteria": (
            f"Antwort auf TF4: funktioniert mit {shortest} Tagen: {'ja' if summary.works else 'nein'} "
            "(Prognose, keine Fehlfunktion, Erkennung)",
            build_criteria_table(summary.criteria),
        ),
        "result_totals": (
            f"Kennzahlen insgesamt: {shortest} gegenüber {longest} Tagen Kaltstart, alle Termine",
            build_totals_table(
                summary.totals,
                shortest=shortest,
                longest=longest,
                adaptive_model_id=adaptive_model_id,
                static_model_id=static_model_id,
                reference_model_id=reference_model_id,
            ),
        ),
        "result_weeks": (
            f"Einpegeln: {shortest} gegenüber {longest} Tagen Kaltstart je Woche nach Start",
            build_week_table(
                summary.weeks,
                shortest=shortest,
                longest=longest,
                adaptive_model_id=adaptive_model_id,
            ),
        ),
        "result_settling": (
            "Einschwingwoche: erste Woche, ab der es keine Abweichung mehr gibt",
            build_settling_table(summary.settling),
        ),
    }


def build_injection_table(matrix: pd.DataFrame) -> pd.DataFrame:
    keys = matrix[["scenario", "injection_day"]]
    runs = matrix.drop(columns=["scenario", "injection_day"])
    runs.columns = [
        f"{start}, {days} Tage"
        for start, days in (column.split("_") for column in runs.columns)
    ]

    return pd.concat(
        [
            relabel(keys, KEY_HEADERS, VALUE_LABELS),
            runs.map(lambda detected: CHECKED if detected else MISSED),
        ],
        axis=1,
    )


def build_appendix(
    summary: E4Summary,
    *,
    shortest: int,
    longest: int,
    adaptive_model_id: str,
    static_model_id: str,
    reference_model_id: str,
) -> dict[str, tuple[str, pd.DataFrame]]:
    weeks = summary.forecast.weeks

    return {
        "result_forecast_weeks": (
            f"Prognose je Woche nach Start: Tagesfehler {adaptive_model_id} minus Vergleichsmodell [W], negativ = {adaptive_model_id} besser",
            pd.DataFrame(
                {
                    "Woche": weeks["week"],
                    f"{shortest} Tage: {adaptive_model_id} minus {static_model_id}": weeks[
                        f"minus_static_{shortest}"
                    ],
                    f"{longest} Tage: {adaptive_model_id} minus {static_model_id}": weeks[
                        f"minus_static_{longest}"
                    ],
                    f"{shortest} Tage: {adaptive_model_id} minus {reference_model_id}": weeks[
                        f"minus_reference_{shortest}"
                    ],
                    f"{longest} Tage: {adaptive_model_id} minus {reference_model_id}": weeks[
                        f"minus_reference_{longest}"
                    ],
                    f"{adaptive_model_id}: {shortest} Tage minus {longest} Tage": weeks[
                        f"gap_{shortest}"
                    ],
                }
            ),
        ),
        "result_injections": (
            f"Eingebaute Tage: {CHECKED} = Klasse am Tag nach dem Injektionstag ist die erwartete, {MISSED} = nicht",
            build_injection_table(summary.system.injection_matrix),
        ),
    }


def build_notes(
    summary: E4Summary, *, adaptive_model_id: str, shortest: int
) -> list[str]:
    overall = summary.forecast.overall
    mape = overall.loc[overall["coldstart_days"].eq(shortest), "mape_pct"].iloc[0]
    cycle = ", ".join(
        f"{row['coldstart_days']} Tage {format_number(row['max_mae_difference_w'], STANDARD_CONFIG.decimals)} W"
        for row in summary.cycle_forecast.to_dict("records")
    )

    return [
        "Tag 0 = erster prognostizierter Tag, eingeordnet wird an ihm der letzte Tag der Start-Historie. Ein Injektionstag k wird am Tag k + 1 eingeordnet",
        f"Als Meldung zählen die Klassen {', '.join(NOTIFICATION_CLASSIFICATIONS)}, low und unknown nicht. Falsch und verpasst sind Abweichungen vom langen Kaltstart am selben Tag im sauberen Lauf. Es sind echte Daten, eine Meldung nur beim kurzen Kaltstart kann also auch berechtigt sein",
        "Anomalie erkannt: am Tag nach dem Injektionstag ist die Klasse die erwartete, Wahrheit ist die eingebaute Injektion. Der lange Kaltstart erkennt selbst nur einen Teil",
        "Falsche new_pattern: Läufe, sauber und mit Injektion, in denen der kurze Kaltstart zurücksetzt und der lange am selben Tag nicht",
        "Einschwingwoche: Prognose nach der 2-Standardfehler-Regel, Meldungen und Resets nach jeder Abweichung, Erkennung nach jeder Injektion, die nur der lange Kaltstart erkennt. Erkennung ist nur bis zur letzten Injektionswoche belegt",
        f"MAPE {adaptive_model_id} mit {shortest} Tagen: {format_number(mape, STANDARD_CONFIG.decimals)} % (Proposal-Kriterium 10 %, hier kein Maßstab)",
        f"Kontrolle Prognose im Kreislauf gegen Walk-Forward bis zum ersten Reset, soll 0 sein: größte Abweichung {cycle}",
        NOISE_RULE_NOTE,
        "Einschränkungen: ein Haushalt, wenige Termine, aufeinanderfolgende Tage sind nicht unabhängig (Standardfehler eher zu klein), "
        "LLM mit Temperatur 0 als deterministisch angenommen (Ollama auf GPU nicht garantiert bitgenau)",
    ]


def main() -> None:
    run_directory = run_directory_from_argv(PROJECT_CONFIG.e4_output_dir, RUN_PREFIX)
    run_config = read_raw_json(run_directory, "run_config")
    e4_config = run_config["e4_config"]
    adaptive_model_id = run_config["prophet_variant"]["model_id"]
    static_model_id = e4_config["static_variant"]["model_id"]
    reference_model_id = run_config["reference_baseline"]
    shortest = min(e4_config["coldstart_days"])
    longest = max(e4_config["coldstart_days"])

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
        reference_model_id=reference_model_id,
        week_days=e4_config["week_days"],
        smoothing_days=e4_config["smoothing_days"],
    )

    output_directory = user_output_directory(run_directory)
    build_e4_forecast_plot(
        summary.forecast.curve,
        output_directory,
        adaptive_model_id=adaptive_model_id,
        static_model_id=static_model_id,
        reference_model_id=reference_model_id,
        smoothing_days=e4_config["smoothing_days"],
    )

    write_result_report(
        output_directory,
        title=f"E4 Kaltstart, Lauf {run_directory.name}",
        setup=build_setup(run_config),
        tables=build_tables(
            summary,
            shortest=shortest,
            longest=longest,
            adaptive_model_id=adaptive_model_id,
            static_model_id=static_model_id,
            reference_model_id=reference_model_id,
        ),
        notes=build_notes(
            summary, adaptive_model_id=adaptive_model_id, shortest=shortest
        ),
        images=["e4_forecast.png"],
        decimals=STANDARD_CONFIG.decimals,
        appendix=build_appendix(
            summary,
            shortest=shortest,
            longest=longest,
            adaptive_model_id=adaptive_model_id,
            static_model_id=static_model_id,
            reference_model_id=reference_model_id,
        ),
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
