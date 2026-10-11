# conda activate forecasting-env
# python -m experiments.e3_system_compare.e3_report [run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_e3_system_compare import (
    WeekPanel,
    build_e3_plot,
    build_e3_week_plot,
)
from experiments.common.harness import read_llm_outputs, read_run_meta
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    answer_bullets,
    format_commit,
    format_cutovers,
    forecast_error_table,
    write_explanation_rating_template,
    write_result_report,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.e3_system_compare.e3_config import (
    RESULTS_FILE,
    RUN_PREFIX,
)
from experiments.e3_system_compare.e3_evaluation import E3Summary, summarize_e3
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

SERIES_LABELS = {
    "control": "Kontrolllauf",
    "scaled": "Sprung hoch",
    "scaled_down": "Sprung runter",
    "ramp_28": "Rampe hoch",
    "ramp_28_down": "Rampe runter",
}


def event_labels(event_series: dict[str, list]) -> dict[int, str]:
    events = [
        event for series_events in event_series.values() for event in series_events
    ]
    return {
        number: f"{number}: {KIND_LABELS[kind]}, Tag {day}"
        for number, (day, kind) in enumerate(events, start=1)
    }


OVERVIEW_ROWS = (
    ("Fälle mit Reset (Cutover × Reihe)", "triggered_cases", "cases"),
    ("Tagesfehler ab dem Reset [W], auf denselben Tagen", "day_error_w", "number"),
    ("Differenz gegen {reference} [W]", "day_error_delta_w", "number"),
    ("2 Standardfehler der Differenz [W]", "day_error_delta_two_se_w", "number"),
    ("gepaarte Tage", "paired_days", "count"),
    ("Differenz belastbar", "day_error_reliable", "yes_no"),
    ("Meldungstage, alle Fälle zusammen", "notification_days", "count"),
    ("unknown-Tage (blind), alle Fälle zusammen", "unknown_days", "count"),
    (
        "Meldungen je 30 Tage nach dem Reset",
        "notifications_per_period",
        "number",
    ),
    ("Differenz gegen {reference}", "notification_delta", "number"),
    ("Resets im Kontrolllauf (Fehlalarme)", "control_resets", "count"),
    ("{llm} besser als {reference} (Fälle mit Reset)", "better_cases", "share"),
)


def build_overview_table(
    overall: pd.DataFrame, *, reference: str, llm: str
) -> pd.DataFrame:
    systems = {row["config"]: row for row in overall.to_dict("records")}

    def cell(config: str, column: str, kind: str) -> object:
        value = systems[config][column]
        if pd.isna(value):
            return "-"
        if kind == "yes_no":
            return YES_NO[bool(value)]
        if kind == "count":
            return int(value)
        if kind == "cases":
            return f"{int(value)}/{int(systems[config]['cases'])}"
        if kind == "share":
            return f"{int(value)}/{int(systems[config]['triggered_cases'])}"
        return float(value)

    rows: dict[str, list[object]] = {
        "Kennzahl": [
            label.format(reference=reference, llm=llm) for label, _, _ in OVERVIEW_ROWS
        ]
    }
    for config in systems:
        rows[SYS_LABELS[config]] = [
            cell(config, column, kind) for _, column, kind in OVERVIEW_ROWS
        ]

    return pd.DataFrame(rows, dtype=object)


def build_week_table(
    weeks: pd.DataFrame, *, reference: str, llm: str, by_series: bool = False
) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Woche ab Reset": weeks["week"],
            "Fälle": weeks["cases"],
            f"Tagesfehler {SYS_LABELS[llm]} [W]": weeks["llm_day_error_w"],
            f"Tagesfehler {SYS_LABELS[reference]} [W]": weeks["reference_day_error_w"],
            f"Differenz {llm} − {reference} [W]": weeks["day_error_delta_w"],
        }
    )
    if by_series:
        table.insert(0, "Reihe", weeks["series"].map(SERIES_LABELS))

    return table


def build_case_table(cases: pd.DataFrame, *, reference: str, llm: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": cases["cutover_date"],
            "Reihe": cases["series"].map(SERIES_LABELS),
            f"Reset {llm} an Tag": cases["reset_day"],
            f"Differenz Tagesfehler gegen {reference} [W]": cases["day_error_delta_w"],
            "belastbar": cases["day_error_reliable"].map(YES_NO),
            f"Differenz Meldungen je 30 Tage gegen {reference}": cases[
                "notification_delta"
            ],
            "Resets im Kontrolllauf": cases["control_resets"],
            f"{llm} besser": cases["better"].map(YES_NO),
        }
    )


def build_event_table(events: pd.DataFrame, labels: dict[int, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": events["cutover_date"],
            "Ereignis": events["event"].map(labels),
            "System": events["config"].map(SYS_LABELS),
            "bewertet an Tag": events["judged_day"],
            "Klasse": events["classification"],
            "Skala": events["trigger_scale"],
            "Meldungen davor": events["lead_notification_days"],
            "Reset an Tag": events["reset_day"],
            "nach Trennung": events["after_separation"].map(YES_NO),
        }
    )


def build_forecast_table(forecast: pd.DataFrame, reference: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": forecast["cutover_date"],
            "Zeitraum": [
                f"{SERIES_LABELS[series]} ab Reset an Tag {day}"
                for series, day in zip(forecast["series"], forecast["reset_day"])
            ],
            "System": forecast["config"].map(SYS_LABELS),
        }
    ).join(forecast_error_table(forecast, "Tage", reference))


def build_notification_table(notifications: pd.DataFrame) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Cutover": notifications["cutover_date"],
            "Reihe": notifications["series"].map(SERIES_LABELS),
            "System": notifications["config"].map(SYS_LABELS),
            "Woche ab Reset": notifications["week"],
            "Tage": notifications["days"],
            "Meldungstage": notifications["notification_days"],
        }
    )
    for classification in NOTIFICATION_CLASSIFICATIONS:
        table[f"davon {classification}"] = notifications[f"{classification}_days"]
    table["unknown-Tage"] = notifications["unknown_days"]
    table["Meldungen je 30 Tage"] = notifications["notifications_per_period"]

    return table


def build_control_table(control: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": control["cutover_date"],
            "System": control["config"].map(SYS_LABELS),
            "Tage": control["days"],
            "Meldungen": control["notification_days"],
            "unknown": control["unknown_days"],
            "Resets": control["resets"],
        }
    )


def build_latency_table(latency: pd.DataFrame, reference: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": latency["cutover_date"],
            "Reihe": latency["series"].map(SERIES_LABELS),
            "Tage": latency["days"],
            f"{reference} je Tag [s]": latency["rule_seconds_per_day"],
            "LLM-Aufrufe": latency["llm_calls"],
            "Ausfalltage": latency["failed_days"],
            f"Mehrlaufzeit gegen {reference} [s]": latency["extra_seconds"],
            "je Aufruf [s]": latency["extra_seconds_per_call"],
        }
    )


def answer_lines(answers: pd.DataFrame, labels: dict[int, str]) -> list[str]:
    lines: list[str] = []
    for (cutover_date, series), group in answers.groupby(
        ["cutover_date", "series"], sort=False
    ):
        lines += [f"**{SERIES_LABELS[str(series)]}, Cutover {cutover_date}**", ""]
        for _, row in group.iterrows():
            event = (
                ""
                if pd.isna(row["event"])
                else f", Ereignis {labels[int(row['event'])]}"
            )
            lines += [
                f"{row['analyzed_day']} (Entscheidungstag {row['days_since_cutover']}{event}): "
                f"{row['config']} {row['classification']}, Aktion {row['adaption_action']}",
                "",
            ] + answer_bullets(
                row["explanation"], row["user_recommendation"], row["uncertainty"]
            )
            lines.append("")

    return lines


def build_setup(
    e3_config: dict,
    standard_config: dict,
    llm_config: dict,
    labels: dict[int, str],
    code_version: dict,
) -> dict[str, str]:
    return {
        "Cutover": format_cutovers(
            standard_config, e3_config["cutovers"][standard_config["split"]]
        )
        + " (Tag 0, alle Tage und Daten in Ortszeit)",
        "Fenster": f"{standard_config['monitoring_before_cutover_days']} Tage vor und "
        f"{standard_config['margin_after_days']} Tage ab Cutover",
        "Ereignisse": "; ".join(labels.values()),
        "Systeme": ", ".join(
            SYS_LABELS[e3_config[key]] for key in ("reference_system", "llm_system")
        ),
        f"LLM {e3_config['llm_system']}": f"{llm_config['model']}, Prompt {llm_config['prompt_version']}",
        "Kalender": "keiner, wie CTX0",
        "Commit": format_commit(code_version),
    }


def build_notes(summary: E3Summary, *, reference: str, llm: str) -> list[str]:
    notes = [
        "Tag = Entscheidungstag seit Cutover: an Tag n wird Tag n-1 eingeordnet, ein Ereignis an Tag s also ab Tag s+1",
        f"Fall = Cutover × Reihe mit Ereignis. Ein Fall zählt in die Hauptzahlen, wenn {llm} in der Reihe zurückgesetzt hat (Reset an Tag). Erkennung und Einordnung werden in E1 und E2 geprüft, hier nur als Beleg in der Ereignistabelle",
        f"Tagesfehler: ab dem Reset-Tag, denn die Prognose desselben Tages enthält den Reset schon. {reference} wird auf denselben Tagen gepaart, nie zurückgesetzt",
        f"Meldungen: Tage nach dem Reset-Tag von {llm}, bei beiden Systemen auf denselben Tagen. Als Meldung zählen peak, new_pattern und measurement_error",
        "Woche ab Reset: Woche 1 sind die ersten Tage ab dem Reset. Später gehen Fälle mit weniger Tagen im Fenster verloren, die Spalte Fälle zeigt das",
        "bewertet an Tag: bei der Dauerlast der erste Tag mit Drift oder new_pattern. Meldungen davor zählen als Meldungen, nicht als Einordnungsfehler",
        "nach Trennung: vor Beginn des Ereignisses hat schon ein System anders gehandelt (Reset), die Systeme entscheiden dann nicht mehr über denselben Zustand",
        "Kontrolllauf über das ganze Fenster, auch die Tage vor dem Cutover. Jede Meldung dort ist ein Fehlalarm, jeder Reset unnötig",
        NOISE_RULE_NOTE,
    ]

    for row in summary.separations.loc[
        ~summary.separations["forecast_identical_before"]
    ].to_dict("records"):
        notes.append(
            f"Plausibilitätsprüfung verletzt: im {SERIES_LABELS[row['series']]} {row['cutover_date']} "
            "unterscheiden sich die Prognosen schon vor der ersten abweichenden Aktion"
        )
    if summary.interrupted:
        notes.append(
            "Mindestens ein System wurde abgebrochen, der Lauf ist nicht auswertbar"
        )

    return notes


def build_week_panels(summary: E3Summary) -> list[WeekPanel]:
    # eine Spalte je Reihe, in der Reihenfolge der Auswertung
    return [
        WeekPanel(
            title=SERIES_LABELS[str(series)],
            forecast=weeks,
            case_forecast=summary.forecast_weeks_by_case.loc[
                summary.forecast_weeks_by_case["series"].eq(series)
            ],
            notifications=summary.notifications_weeks_by_series.loc[
                summary.notifications_weeks_by_series["series"].eq(series)
            ],
            case_notifications=summary.notifications_weeks.loc[
                summary.notifications_weeks["series"].eq(series)
            ],
        )
        for series, weeks in summary.forecast_weeks_by_series.groupby(
            "series", sort=False
        )
    ]


def write_report(run_directory: Path) -> Path:
    raw_directory = run_directory / RAW_SUBDIR
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    reference = e3_config["reference_system"]
    llm = e3_config["llm_system"]
    labels = event_labels(e3_config["event_series"])

    results = pd.read_csv(
        raw_directory / f"{RESULTS_FILE}.csv", dtype={"cutover_date": str}
    )
    llm_outputs = read_llm_outputs(raw_directory)
    summary = summarize_e3(
        results,
        read_run_meta(raw_directory),
        llm_outputs,
        event_series=e3_config["event_series"],
        reference_system=reference,
        llm_system=llm,
        week_days=e3_config["week_days"],
    )
    tables = {
        "result_overview": (
            f"Hilft die Adaption? {llm} gegen {reference}, nur Fälle mit Reset von {llm}",
            build_overview_table(summary.overall, reference=reference, llm=llm),
        ),
        "result_forecast_weeks": (
            "Tagesfehler je Woche ab dem Reset, alle Fälle mit Reset zusammen",
            build_week_table(summary.forecast_weeks, reference=reference, llm=llm),
        ),
    }
    appendix = {
        "result_forecast_weeks_by_series": (
            "Tagesfehler je Woche ab dem Reset, je Reihe",
            build_week_table(
                summary.forecast_weeks_by_series,
                reference=reference,
                llm=llm,
                by_series=True,
            ),
        ),
        "result_cases": (
            "Fälle je Cutover und Reihe",
            build_case_table(summary.cases, reference=reference, llm=llm),
        ),
        "result_events": (
            "Erste Einordnung je Ereignis",
            build_event_table(summary.events, labels),
        ),
        "result_forecast": (
            f"Prognose ab dem Reset je Fall, gepaart gegen {reference}",
            build_forecast_table(summary.forecast, reference),
        ),
        "result_notifications": (
            "Meldungen nach dem Reset je Fall und Woche ab Reset, Meldungstage nach Klasse",
            build_notification_table(summary.notifications_weeks),
        ),
        "result_control": (
            "Kontrolllauf: Fehlalarme und unnötige Resets",
            build_control_table(summary.control),
        ),
        "result_latency": (
            f"Laufzeit und Kosten {llm}, nur beschreibend",
            build_latency_table(summary.latency, reference),
        ),
    }

    output_directory = user_output_directory(run_directory)
    build_e3_plot(
        results,
        output_directory,
        event_days={
            series: [day for day, _ in events]
            for series, events in e3_config["event_series"].items()
        },
        series_labels=SERIES_LABELS,
    )
    build_e3_week_plot(
        [
            WeekPanel(
                title="alle Fälle mit Reset zusammen",
                forecast=summary.forecast_weeks,
                case_forecast=summary.forecast_weeks_by_case,
                notifications=summary.notifications_weeks_pooled,
                case_notifications=summary.notifications_weeks,
            )
        ],
        output_directory,
        name="e3_weeks",
        reference=reference,
        llm=llm,
    )
    series_panels = build_week_panels(summary)
    if series_panels:
        build_e3_week_plot(
            series_panels,
            output_directory,
            name="e3_weeks_by_series",
            reference=reference,
            llm=llm,
        )
    write_explanation_rating_template(llm_outputs, output_directory)

    write_result_report(
        output_directory,
        title=f"E3 Adaption {reference} gegen {llm}, Lauf {run_directory.name}",
        setup=build_setup(
            e3_config,
            run_config["standard_config"],
            run_config["llm_config"],
            labels,
            run_config["code_version"],
        ),
        tables=tables,
        notes=build_notes(summary, reference=reference, llm=llm),
        images=["e3_weeks.png"],
        decimals=STANDARD_CONFIG.decimals,
        appendix=appendix,
        appendix_text=[
            (
                "Wochenverlauf je Reihe",
                ["![e3_weeks_by_series](e3_weeks_by_series.png)"],
            ),
            ("Tagesfehler je Cutover und Reihe", ["![e3_timeline](e3_timeline.png)"]),
            ("Antworten des LLM", answer_lines(summary.answers, labels)),
        ],
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e3_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
