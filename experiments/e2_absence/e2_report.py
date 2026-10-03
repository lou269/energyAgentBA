# conda activate forecasting-env
# python -m experiments.e2_absence.e2_report [full|precheck] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_e2_absence import build_e2_plot
from experiments.common.harness import (
    FORECASTS_FILE,
    read_anomaly_rows,
    read_calendar_availability,
    read_llm_outputs,
)
from experiments.common.report import (
    format_commit,
    key_figures_table,
    write_explanation_rating_template,
    write_result_report,
)
from experiments.common.standard_config import DECIMALS, LOCAL_TIMEZONE, PROJECT_CONFIG
from experiments.e2_absence.e2_config import (
    COMPARISON_FILE,
    PRECHECK_RUN_PREFIX,
    REDUCTION_FILE,
    RUN_PREFIX,
)
from experiments.e2_absence.e2_evaluation import (
    E2Summary,
    GatePrecheckSummary,
    summarize_e2,
    summarize_gate_precheck,
)
from experiments.e2_absence.e2_selection import (
    load_calendar_events,
    resolve_absence_window,
)
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

CONFIG_LABELS = {
    "SYS1": "SYS1 ohne Adaption",
    "SYS2": "SYS2 Regel",
    "SYS3_CTX0": "SYS3 ohne Kalender",
    "SYS3_CTX1": "SYS3 mit Kalender",
    "SYS3_CTX2": "SYS3 Kalender per Tool",
}

PHASE_LABELS = {
    "before": "vor dem Urlaub",
    "absence": "Urlaub",
    "after_return": "nach der Rückkehr",
}


def read_ctx_anomaly(raw_directory: Path, ctx_systems: dict) -> pd.DataFrame:
    return pd.concat(
        [read_anomaly_rows(raw_directory / ctx) for ctx in ctx_systems],
        ignore_index=True,
    )


def build_absence_table(
    absence_classification: pd.DataFrame, target_classification: str
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": absence_classification["config"],
            "Urlaubstage": absence_classification["absence_days"],
            "Treffer": [
                f"{hits} von {gate_open}"
                for hits, gate_open in zip(
                    absence_classification["hit_days"],
                    absence_classification["gate_open_days"],
                )
            ],
            "erster Treffer [Urlaubstag]": absence_classification["first_hit_day"],
            f"{target_classification} ohne Beleg": absence_classification[
                "unsupported_absence_days"
            ],
        }
    )


def build_calendar_table(calendar_use: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": calendar_use["config"],
            "Phase": calendar_use["phase"].map(PHASE_LABELS),
            "eingeordnete Tage": calendar_use["classified_days"],
            "davon Kalender im State": calendar_use["calendar_days"],
        }
    )


def build_forecast_table(forecast: pd.DataFrame, reference_config: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": forecast["config"],
            "Phase": forecast["phase"].map(PHASE_LABELS),
            "MAE [W]": forecast["mean_mae_w"],
            f"Differenz zu {reference_config} [W]": forecast["mean_delta"],
            "Standardfehler [W]": forecast["delta_standard_error"],
            "Anteil Tage besser": forecast["better_share"],
            "gepaarte Tage": forecast["paired_count"],
        }
    )


def build_reduction_table(reduction: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Datum": reduction["date"],
            "Mains [W]": reduction["mains_before_w"],
            "ohne Kanäle [W]": reduction["mains_after_w"],
            "Absenkung [W]": reduction["reduction_w"],
        }
    )


def build_setup(
    e2_config: dict,
    summary: E2Summary,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    code_version: dict,
) -> dict[str, str]:
    setup = {
        "Abwesenheit": (
            f"{e2_config['active_absence_event_id']}, {window_start.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d} "
            f"bis vor {window_end.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d}, Beginn = Tag 0"
        ),
        "Analysierte Tage": f"{summary.first_analyzed_day} bis {summary.last_analyzed_day}",
        "Kanäle": f"im Urlaubsfenster aus Mains herausgerechnet, Coverage ab {e2_config['min_coverage_share_for_subtraction'] * 100:.0f} %",
    }
    for ctx, systems in e2_config["ctx_systems"].items():
        setup[f"Systeme {ctx}"] = ", ".join(systems)
    setup["Commit"] = format_commit(code_version)

    return setup


def build_key_figures(summary: E2Summary, target_classification: str) -> pd.DataFrame:
    rows = [
        (
            f"{row['config']}: erster Treffer {target_classification} [Urlaubstag]",
            row["first_hit_day"],
            f"{row['hit_days']} von {row['gate_open_days']} Urlaubstagen mit offenem Gate, "
            f"{row['unsupported_absence_days']} × {target_classification} ohne Beleg",
        )
        for row in summary.absence_classification.to_dict("records")
    ]
    rows.append(
        (
            "Absenkung durch das Herausrechnen im Mittel [W]",
            summary.mean_reduction_w,
            "je Tag im Urlaubsfenster",
        )
    )

    return key_figures_table(rows)


def build_precheck_first_days_table(summary: GatePrecheckSummary) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": summary.first_days["config"],
            "Gate offen [Urlaubstag]": summary.first_days["first_gate_open_day"],
            "Drift [Urlaubstag]": summary.first_days["first_drift_day"],
            "Reset [Urlaubstag]": summary.first_days["first_reset_day"],
        }
    )


def build_phase_table(phases: pd.DataFrame, target_classification: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": phases["config"],
            "Phase": phases["phase"].map(PHASE_LABELS),
            "Tage": phases["days"],
            "Gate offen": phases["gate_open_days"],
            "davon Einzeltag": phases["alarm_days"],
            "davon Drift": phases["drift_gate_days"],
            "new_pattern": phases["new_pattern_days"],
            "low": phases["low_days"],
            "peak": phases["peak_days"],
            target_classification: phases["absence_classified_days"],
            "Resets": phases["reset_days"],
            "Meldungen": phases["notification_days"],
            "Ausfalltage": phases["failed_days"],
            "MAE [W]": phases["mean_mae_w"],
        }
    )


def build_precheck_days_table(summary: GatePrecheckSummary) -> pd.DataFrame:
    days = summary.days_from_absence
    return pd.DataFrame(
        {
            "System": days["config"],
            "Urlaubstag": days["absence_day"],
            "Datum": days["analyzed_day"],
            "Phase": days["phase"].map(PHASE_LABELS),
            "Tagesmittel [W]": days["today_mean"],
            "erwartet Wochentag [W]": days["weekday_expected"],
            "z daily": days["daily_score"],
            "z weekday": days["weekday_score"],
            "z weekly": days["weekly_score"],
            "long_term [%]": days["long_term_deviation_pct"],
            "Streak weekly": days["weekly_anomaly_streak_days"],
            "Streak long_term": days["long_term_anomaly_streak_days"],
            "Level": days["anomaly_level"],
            "Drift": days["sustained_drift"],
            "Einordnung": days["classification"],
            "Adaption": days["adaption_action"],
            "MAE [W]": days["mae_w"],
        }
    )


def write_full_report(run_directory: Path) -> None:
    run_config = read_raw_json(run_directory, "run_config")
    e2_config = run_config["e2_config"]
    target_classification = e2_config["target_classification"]

    calendar_events = load_calendar_events(Path(e2_config["calendar_events_file"]))
    window_start, window_end = resolve_absence_window(
        calendar_events, e2_config["active_absence_event_id"]
    )

    raw_directory = run_directory / RAW_SUBDIR
    comparison = pd.read_csv(
        raw_directory / f"{COMPARISON_FILE}.csv", parse_dates=["decision_time"]
    )
    reduction = pd.read_csv(raw_directory / f"{REDUCTION_FILE}.csv")
    summary = summarize_e2(
        comparison,
        read_ctx_anomaly(raw_directory, e2_config["ctx_systems"]),
        pd.concat(
            [
                read_calendar_availability(raw_directory / ctx)
                for ctx in e2_config["ctx_systems"]
            ],
            ignore_index=True,
        ),
        pd.concat(
            [
                pd.read_csv(raw_directory / ctx / FORECASTS_FILE)
                for ctx in e2_config["ctx_systems"]
            ],
            ignore_index=True,
        ),
        reduction,
        window_start=window_start,
        window_end=window_end,
        target_classification=target_classification,
        absence_event_id=e2_config["active_absence_event_id"],
        reference_config=e2_config["reference_config"],
    )

    output_directory = user_output_directory(run_directory)
    build_e2_plot(
        summary.timeline,
        output_directory,
        configs=tuple(e2_config["plot_configs"]),
        config_labels=CONFIG_LABELS,
    )
    write_result_report(
        output_directory,
        title=f"E2 Abwesenheit, Lauf {run_directory.name}",
        setup=build_setup(
            e2_config, summary, window_start, window_end, run_config["code_version"]
        ),
        tables={
            "key_figures": (
                "Kennzahlen",
                build_key_figures(summary, target_classification),
            ),
            "result_phases": (
                "Einordnung je Phase",
                build_phase_table(summary.phases, target_classification),
            ),
            "result_absence": (
                "Einordnung im Urlaub",
                build_absence_table(
                    summary.absence_classification, target_classification
                ),
            ),
            "result_calendar": (
                "Kalender im State",
                build_calendar_table(summary.calendar_use),
            ),
            "result_forecast": (
                "Prognose je Phase",
                build_forecast_table(summary.forecast, e2_config["reference_config"]),
            ),
        },
        notes=[
            "Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag",
            f"Treffer = {target_classification} mit passendem Kalendereintrag. {target_classification} ohne Beleg (ohne Kalender, "
            "Kalender nicht abgerufen oder nach der Rückkehr) zählt als Fehlklassifikation, über alle Phasen",
            "Treffer: von den Urlaubstagen mit offenem Gate, an den übrigen wird nicht eingeordnet. Wenige Tage, deshalb als Anzahl",
            "Einordnung je Phase: im Urlaub ist jede Meldung außer einem Treffer ein Fehlalarm, Ausfalltage = LLM ohne gültige Antwort",
            f"Differenz zu {e2_config['reference_config']}: gepaart am selben Tag, negativ = besser",
            "ctx0 ohne, ctx1 mit Kalender im State, ctx2 Kalender per Tool. SYS1 und SYS2 lesen keinen Kalender und laufen nur in ctx0",
            "Kalender im State: bei ctx2 hat das LLM an diesen Tagen nachgeschaut, jeder ctx2-Tag mit LLM kostet einen zusätzlichen Aufruf für die Tool-Entscheidung",
        ],
        images=["e2_timeline.png"],
        decimals=DECIMALS,
        appendix={
            "result_reduction": (
                "Absenkung je Tag im Urlaubsfenster",
                build_reduction_table(summary.reduction),
            ),
        },
    )
    write_explanation_rating_template(
        read_llm_outputs(run_directory / RAW_SUBDIR), output_directory
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


def write_precheck_report(run_directory: Path) -> None:
    run_config = read_raw_json(run_directory, "run_config")
    e2_config = run_config["e2_config"]

    calendar_events = load_calendar_events(Path(e2_config["calendar_events_file"]))
    window_start, window_end = resolve_absence_window(
        calendar_events, e2_config["active_absence_event_id"]
    )

    raw_directory = run_directory / RAW_SUBDIR
    comparison = pd.read_csv(raw_directory / f"{COMPARISON_FILE}.csv")
    summary = summarize_gate_precheck(
        comparison,
        read_ctx_anomaly(raw_directory, e2_config["ctx_systems"]),
        window_start=window_start,
        window_end=window_end,
        target_classification=e2_config["target_classification"],
        absence_event_id=e2_config["active_absence_event_id"],
    )

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"E2 Vorprüfung Gate, Lauf {run_directory.name}",
        setup={
            "Abwesenheit": (
                f"{e2_config['active_absence_event_id']}, {window_start.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d} "
                f"bis vor {window_end.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d}"
            ),
            "Systeme": ", ".join(e2_config["ctx_systems"]["ctx0"]),
            "Tage nach der Rückkehr": str(e2_config["decision_time_margin_after_days"]),
            "Commit": format_commit(run_config["code_version"]),
        },
        tables={
            "precheck_first_days": (
                "Erste Tage ab Urlaubsbeginn",
                build_precheck_first_days_table(summary),
            ),
            "precheck_phases": (
                "Gate und Einordnung je Phase",
                build_phase_table(summary.phases, e2_config["target_classification"]),
            ),
        },
        notes=[
            "Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag",
            "Gate Einzeltag: daily/weekday über ihrer Schwelle, Gate Drift: sustained_drift (Streak auf mindestens zwei Niveau-Skalen)",
            "Reset = new_pattern mit advance_history_start, bei SYS1 nie",
        ],
        images=[],
        decimals=DECIMALS,
        appendix={
            "precheck_days": (
                "Je Tag ab Urlaubsbeginn",
                build_precheck_days_table(summary),
            ),
        },
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "full"

    if part == "precheck":
        write_precheck_report(
            run_directory_from_argv(
                PROJECT_CONFIG.e2_output_dir, PRECHECK_RUN_PREFIX, 2
            )
        )
    else:
        write_full_report(
            run_directory_from_argv(PROJECT_CONFIG.e2_output_dir, RUN_PREFIX, 2)
        )


if __name__ == "__main__":
    main()
