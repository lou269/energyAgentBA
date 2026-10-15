# conda activate forecasting-env
# python -m experiments.k1_detection.k1_report [run_directory]

from pathlib import Path

import pandas as pd

from experiments.common.report import (
    DETECTION_LABELS,
    KIND_LABELS,
    build_setup,
    format_number,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.k1_detection.k1_config import (
    DIAGNOSIS_FILE,
    GRID_FILE,
    RESETS_FILE,
    RUN_PREFIX,
    SINGLE_DAY_FILE,
    STREAK_THRESHOLD_COLUMNS,
)
from experiments.k1_detection.k1_evaluation import K1Summary, summarize_k1
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

GRID_HEADERS = {
    "share": "Anteil anhaltender Tage",
    "weekly_streak_threshold": "Schwelle weekly",
    "long_term_streak_threshold_pct": "Schwelle long_term [%]",
    "resets": "Resets",
    "resets_per_year": "Resets je Jahr",
    "selected": "gewählt",
}
SINGLE_DAY_HEADERS = {
    "threshold": "Schwelle",
    "alarm_share": "Tage mit Alarm [%]",
}
DIAGNOSIS_HEADERS = {
    "kind": "Szenario",
    "expected": "soll",
    "chosen_resets": "Reset wegen des Szenarios",
    "chosen_day": "Tage bis zum Reset",
    "chosen_alarms": "Ereignistag gemeldet",
}


def format_thresholds(thresholds: pd.Series | dict) -> str:
    return " / ".join(
        format_number(float(thresholds[column]), 2)
        for column in STREAK_THRESHOLD_COLUMNS.values()
    )


def _ratio(hits: pd.Series, total: pd.Series) -> list[str]:
    return [f"{int(hit)}/{int(count)}" for hit, count in zip(hits, total)]


def build_grid_table(grid: pd.DataFrame) -> pd.DataFrame:
    return grid.assign(selected=grid["selected"].map({True: "ja", False: ""}))[
        list(GRID_HEADERS)
    ].rename(columns=GRID_HEADERS)


def build_single_day_table(single_day: pd.DataFrame) -> pd.DataFrame:
    chosen = single_day.loc[single_day["selected"]]

    return chosen.assign(alarm_share=chosen["alarm_share"] * 100)[
        list(SINGLE_DAY_HEADERS)
    ].rename(columns=SINGLE_DAY_HEADERS)


def build_reset_table(resets: pd.DataFrame, share: float) -> pd.DataFrame:
    chosen = resets.loc[resets["share"].eq(share), "analyzed_day"]

    return pd.DataFrame({"Reset am": chosen.dt.strftime("%d.%m.%Y")})


def build_diagnosis_table(diagnosis: pd.DataFrame, kinds: list[str]) -> pd.DataFrame:
    chosen = (
        diagnosis.loc[diagnosis["config"].eq("chosen")].set_index("kind").loc[kinds]
    )

    return pd.DataFrame(
        {
            "kind": [KIND_LABELS[kind] for kind in kinds],
            "expected": chosen["expected"].map(DETECTION_LABELS).to_numpy(),
            "chosen_resets": _ratio(chosen["own_resets"], chosen["windows"]),
            "chosen_day": chosen["median_reset_day"].to_numpy(),
            "chosen_alarms": _ratio(chosen["event_alarms"], chosen["windows"]),
        }
    )


def build_study_setup(run_config: dict, k1_config: dict, run_name: str) -> dict:
    analysis = run_config["analysis"]
    detector = run_config["numerical_analysis_config"]

    return build_setup(
        run_name,
        run_config["standard_config"],
        None,
        run_config["code_version"],
        systems="Analyse, Streak, Einordnung nach Regel und Reset wie im Zyklus, ohne Prognose und ohne Sprachmodell",
        details={
            "Zeitraum": (
                f"{analysis['first_day']} bis {analysis['last_day']} ({analysis['days']} Tage, validation), "
                "durchgehend mit Reset, Historie davor aus train"
            ),
            "Regel": (
                f"weekly und long_term halten ohne Reset an gleich vielen Tagen an ({detector['sustained_anomaly_streak_days']} "
                f"von {detector['streak_tolerance_window_days']} Tagen über der Schwelle). Gewählt wird der größte Anteil mit "
                f"höchstens {k1_config['max_resets']} Resets"
            ),
            "Einzeltag-Schwelle": (
                f"ein Wert für daily und weekday: der größte Score des Tages schlägt an dem Anteil der {analysis['days']} Tage an, "
                f"der am nächsten bei {format_number(k1_config['single_day_target_share'] * 100, 0)} % liegt. "
                "Scores aus dem durchgehenden Lauf mit Reset und den gewählten Niveau-Schwellen"
            ),
            "Kontrolle": (
                f"Szenarien an {len(analysis['cutovers'])} Zeitpunkten im Abstand von {STANDARD_CONFIG.margin_after_days} Tagen, "
                f"je {STANDARD_CONFIG.monitoring_before_cutover_days} Tage davor und {STANDARD_CONFIG.margin_after_days} danach. "
                "Nicht Teil der Wahl"
            ),
        },
    )


def build_summary(summary: K1Summary, run_config: dict, k1_config: dict) -> list[str]:
    selected = summary.selected
    current = run_config["analysis"]["current_thresholds"]

    return [
        f"Gewählt: weekly / long_term % = {format_thresholds(selected)} bei Anteil {format_number(selected['share'], 2)} "
        f"(aktuelle Config {format_thresholds({STREAK_THRESHOLD_COLUMNS[scale]: value for scale, value in current.items()})})",
        f"Einzeltag-Schwelle = {format_number(summary.single_day_selected['threshold'], 1)} bei "
        f"{format_number(summary.single_day_selected['alarm_share'] * 100, 1)} % Alarmtagen "
        f"(Ziel {format_number(k1_config['single_day_target_share'] * 100, 0)} %, "
        f"aktuelle Config {format_number(run_config['analysis']['current_single_day_threshold'], 1)})",
        f"{selected['resets']} Resets auf validation, {format_number(selected['resets_per_year'], 2)} je Jahr "
        f"(Grenze höchstens {k1_config['max_resets']})",
    ]


def build_notes(run_config: dict) -> list[str]:
    analysis = run_config["analysis"]

    return [
        "Kontrolle, Reset wegen des Szenarios: so oft setzt das System zurück, früher als zur selben Zeit ohne Szenario. Tage bis zum Reset: Median ab dem Ereignistag. Ereignistag gemeldet: der Tag selbst ist auffällig, nur für Spitze und ganzen Tag gedacht",
        "Gezählt wird jeder Reset im durchgehenden Lauf, auch an echten Wechseln (Urlaub, Saison). Die Grenze ist eine Setzung über die Blindzeit nach einem Reset",
        f"Der Anteil anhaltender Tage legt nur das Verhältnis der beiden Schwellen fest. Er wird ohne Reset auf {analysis['days']} Tagen bestimmt, gezählt wird mit Reset",
        f"Kontrolle: Die Zeitpunkte liegen in den Kalibrierdaten, die Zahlen sind eine Ansicht, kein Beleg. Bei {len(analysis['cutovers'])} Zeitpunkten verschiebt schon ein einzelner Fall die Anteile deutlich",
        "Die gewählten Schwellen (weekly_streak_threshold, long_term_streak_threshold_pct, unusual_threshold) sind in NumericalAnalysisConfig zu übernehmen, gerundet",
    ]


def write_report(run_directory: Path) -> Path:
    run_config = read_raw_json(run_directory, "run_config")
    k1_config = run_config["k1_config"]

    raw = run_directory / RAW_SUBDIR
    grid = pd.read_csv(raw / f"{GRID_FILE}.csv")
    resets = pd.read_csv(raw / f"{RESETS_FILE}.csv", parse_dates=["analyzed_day"])
    single_day = pd.read_csv(raw / f"{SINGLE_DAY_FILE}.csv")
    cases = pd.read_csv(raw / f"{DIAGNOSIS_FILE}.csv", dtype={"cutover_date": str})
    summary = summarize_k1(
        grid,
        resets,
        single_day,
        cases,
        days=run_config["analysis"]["days"],
        max_resets=k1_config["max_resets"],
        single_day_target_share=k1_config["single_day_target_share"],
    )

    tables = {
        "result_grid": (
            "Schwellen je Anteil anhaltender Tage und Resets im durchgehenden Lauf",
            build_grid_table(summary.grid),
        ),
        "result_resets": (
            "Resets mit den gewählten Schwellen",
            build_reset_table(resets, summary.selected["share"]),
        ),
        "result_single_day": (
            "Gewählte Einzeltag-Schwelle und Anteil der Tage mit Alarm im durchgehenden Lauf",
            build_single_day_table(summary.single_day),
        ),
        "result_diagnosis": (
            f"Kontrolle mit eingebauten Szenarien an {len(run_config['analysis']['cutovers'])} Zeitpunkten (nicht Teil der Wahl)",
            build_diagnosis_table(
                summary.diagnosis, k1_config["diagnosis_kinds"]
            ).rename(columns=DIAGNOSIS_HEADERS),
        ),
    }

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title="K1: Schwellen der Erkennung",
        summary=build_summary(summary, run_config, k1_config),
        setup=build_study_setup(run_config, k1_config, run_directory.name),
        tables=tables,
        notes=build_notes(run_config),
        images=[],
        decimals=STANDARD_CONFIG.decimals,
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.k1_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
