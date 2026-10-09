# conda activate forecasting-env
# python -m experiments.e3_system_compare.e3_report [run_directory]

from pathlib import Path

import pandas as pd

from docs.plots.plot_e3_system_compare import build_e3_plot
from experiments.common.harness import read_llm_outputs, read_run_meta
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    answer_bullets,
    format_commit,
    format_cutovers,
    format_number,
    forecast_error_table,
    key_figures_table,
    write_explanation_rating_template,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e3_system_compare.e3_config import (
    RESULTS_FILE,
    RUN_PREFIX,
)
from experiments.e3_system_compare.e3_evaluation import (
    ALL_EVENTS,
    E3Summary,
    summarize_e3,
)
from src.config.config_forecasting import SYS_LABELS
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

SERIES_LABELS = {
    "control": "Kontrolllauf",
    "single_days": "Einzeltage-Lauf",
    "scaled": "Dauerlast-Lauf",
}


def event_labels(event_series: dict[str, list]) -> dict[int, str]:
    events = [
        event for series_events in event_series.values() for event in series_events
    ]
    return {
        number: f"{number}: {KIND_LABELS[kind]}, Tag {day}"
        for number, (day, kind) in enumerate(events, start=1)
    }


def build_criteria_table(criteria: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": criteria["config"].map(SYS_LABELS),
            "erwartet": criteria["expected"].replace(ALL_EVENTS, "alle Ereignisse"),
            "erkannt (TF1)": [
                f"{detected}/{events}"
                for detected, events in zip(
                    criteria["prefilter_detected"], criteria["prefilter_events"]
                )
            ],
            "erkannt [%]": criteria["detection_pct"],
            "richtig eingeordnet (TF2)": [
                f"{correct}/{detected}"
                for correct, detected in zip(criteria["correct"], criteria["detected"])
            ],
            "richtig [%]": criteria["correct_pct"],
        }
    )


OVERVIEW_ROWS = (
    ("Teilfrage 1: Hilft die Adaption?", None, ""),
    ("Tagesfehler ab Dauerlast [W], alle Tage der Cutover", "day_error_w", "number"),
    ("Differenz gegen {reference} [W]", "day_error_delta_w", "number"),
    ("2 Standardfehler der Differenz [W]", "day_error_delta_two_se_w", "number"),
    ("Differenz belastbar", "day_error_reliable", "yes_no"),
    (
        "Meldungen je 30 Tage nach Erkennung, insgesamt",
        "notifications_per_period",
        "number",
    ),
    (
        "davon Einzeltag-Anomalien",
        "single_day_notifications_per_period",
        "number",
    ),
    (
        "falsche Resets bei Einzeltag-Ereignissen",
        "single_day_resets",
        "count",
    ),
    ("Resets im Kontrolllauf (Fehlalarme)", "control_resets", "count"),
    ("besser als {reference} (Cutover)", "better_cutovers", "share"),
    ("Teilfrage 2: Macht das LLM es korrekt?", None, ""),
    (
        "zusätzliche Resets im Kontrolllauf gegen {rule}",
        "extra_control_resets",
        "count",
    ),
    ("gleichwertig zu {rule} (Cutover)", "equivalent_cutovers", "share"),
)


def build_overview_table(
    overall: pd.DataFrame, *, reference: str, rule: str
) -> pd.DataFrame:
    systems = {row["config"]: row for row in overall.to_dict("records")}
    cutovers = int(overall["cutovers"].iloc[0])

    def cell(config: str, column: str | None, kind: str) -> object:
        if column is None:
            return ""
        value = systems[config][column]
        if pd.isna(value):
            return "-"
        if kind == "yes_no":
            return YES_NO[bool(value)]
        if kind == "count":
            return int(value)
        if kind == "share":
            return f"{int(value)}/{cutovers}"
        return float(value)

    rows: dict[str, list[object]] = {
        "Kennzahl": [
            label.format(reference=reference, rule=rule)
            for label, _, _ in OVERVIEW_ROWS
        ]
    }
    for config in systems:
        rows[SYS_LABELS[config]] = [
            cell(config, column, kind) for _, column, kind in OVERVIEW_ROWS
        ]

    return pd.DataFrame(rows, dtype=object)


def build_week_table(
    weeks: pd.DataFrame, *, reference: str, others: list[str]
) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "Cutover": weeks["cutover_date"],
            "Woche ab Dauerlast": weeks["week"],
        }
    )
    for config in (reference, *others):
        table[f"Tagesfehler {SYS_LABELS[config]} [W]"] = weeks[
            f"mean_day_error_w_{config}"
        ]
    for config in others:
        table[f"Differenz {SYS_LABELS[config]} gegen {reference} [W]"] = weeks[
            f"mean_delta_{config}"
        ]

    return table


def build_event_table(events: pd.DataFrame, labels: dict[int, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": events["cutover_date"],
            "Ereignis": events["event"].map(labels),
            "System": events["config"].map(SYS_LABELS),
            "erwartet": events["expected"],
            "bewertet an Tag": events["judged_day"],
            "Klasse": events["classification"],
            "richtig": events["correct"].map(YES_NO),
            "Skala": events["trigger_scale"],
            "Meldungen davor": events["lead_notification_days"],
            "Reset an Tag": events["reset_day"],
            "Aktion passend": events["correct_action"].map(YES_NO),
            "nach Trennung": events["after_separation"].map(YES_NO),
        }
    )


def build_forecast_table(forecast: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": forecast["cutover_date"],
            "Zeitraum": [
                f"{SERIES_LABELS[series]} ab Tag {day}"
                for series, day in zip(forecast["series"], forecast["from_day"])
            ],
            "System": forecast["config"].map(SYS_LABELS),
        }
    ).join(forecast_error_table(forecast, "Tage"))


def build_notification_table(notifications: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": notifications["cutover_date"],
            "System": notifications["config"].map(SYS_LABELS),
            "Tage nach Erkennung": notifications["days"],
            "Meldungen Einzeltag-Anomalien": notifications[
                "notification_days_single_day"
            ],
            "Meldungen insgesamt": notifications["notification_days"],
            "Meldungen je 30 Tage": notifications["notifications_per_period"],
        }
    )


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


def build_deviation_table(
    deviations: pd.DataFrame, labels: dict[int, str], *, rule: str, llm: str
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": deviations["cutover_date"],
            "Reihe": deviations["series"].map(SERIES_LABELS),
            "Tag": deviations["days_since_cutover"],
            "Datum": deviations["analyzed_day"],
            "Ereignis": deviations["event"].map(labels),
            f"Klasse {rule}": deviations["classification_rule"],
            f"Klasse {llm}": deviations["classification_llm"],
            f"Aktion {rule}": deviations["adaption_action_rule"],
            f"Aktion {llm}": deviations["adaption_action_llm"],
            "LLM-Ausfall": deviations["llm_failed"].map(YES_NO),
        }
    )


def build_latency_table(latency: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": latency["cutover_date"],
            "Reihe": latency["series"].map(SERIES_LABELS),
            "Tage": latency["days"],
            "Regel je Tag [s]": latency["rule_seconds_per_day"],
            "LLM-Aufrufe": latency["llm_calls"],
            "Ausfalltage": latency["failed_days"],
            "Mehrlaufzeit gegen Regel [s]": latency["extra_seconds"],
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
                f"{row['config']} {row['classification']}, Regel {row['rule_classification']}, "
                f"Aktion {row['adaption_action']}",
                "",
            ] + answer_bullets(
                row["explanation"], row["user_recommendation"], row["uncertainty"]
            )
            lines.append("")

    return lines


def build_key_figures(
    summary: E3Summary, *, reference: str, rule: str, llm: str
) -> pd.DataFrame:
    rows = []
    for row in summary.decisions.to_dict("records"):
        rows += [
            (
                f"{row['cutover_date']}: {system_label} besser als {reference}",
                YES_NO[row[f"{name}_better"]],
                f"Tagesfehler gegen {reference} ab Dauerlast "
                f"{format_number(row[f'{name}_day_error_delta_w'], STANDARD_CONFIG.decimals)} W "
                f"({'belastbar' if row[f'{name}_day_error_reliable'] else 'nicht belastbar'}), "
                f"Meldungen je 30 Tage nach Erkennung "
                f"{format_number(row[f'{name}_notification_delta'], STANDARD_CONFIG.decimals)} gegen {reference}, "
                f"{row[f'{name}_single_day_resets']} Resets bei Einzeltag-Ereignissen, "
                f"{row[f'{name}_control_resets']} im Kontrolllauf",
            )
            for name, system_label in (("rule", rule), ("llm", llm))
        ] + [
            (
                f"{row['cutover_date']}: {llm} gleichwertig zu {rule}",
                YES_NO[row["llm_equivalent"]],
                f"{row['rule_only_correct']} Ereignisse nur {rule} richtig, "
                f"{row['llm_extra_control_resets']} Resets mehr im Kontrolllauf",
            ),
        ]

    return key_figures_table(rows)


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
            SYS_LABELS[e3_config[key]]
            for key in ("reference_system", "rule_system", "llm_system")
        ),
        f"LLM {e3_config['llm_system']}": f"{llm_config['model']}, Prompt {llm_config['prompt_version']}",
        "Kalender": "keiner, wie CTX0",
        "Commit": format_commit(code_version),
    }


def build_notes(summary: E3Summary) -> list[str]:
    notes = [
        "Tag = Entscheidungstag seit Cutover: an Tag n wird Tag n-1 eingeordnet, ein Ereignis an Tag s also ab Tag s+1",
        "bewertet an Tag: bei einer Spitze und beim Festhänger der eingeordnete Ereignistag, falls das Gate dort offen ist, bei der Dauerlast der "
        "erste Tag mit Drift oder new_pattern. Meldungen davor zählen als Meldungen, nicht als Einordnungsfehler. "
        "Ohne Bewertungstag gilt das Ereignis als nicht erkannt und zählt nicht bei der Einordnung. Der Festhänger zählt nicht bei der Erkennung, das Flag öffnet das Gate per Aufbau",
        "nach Trennung: vor Beginn des Ereignisses hat schon ein System anders gehandelt (Reset), die Systeme entscheiden dann nicht mehr über denselben Zustand",
        "Meldungen nach Erkennung: Tage nach dem Bewertungstag der Dauerlast, an denen das System peak, measurement_error oder new_pattern meldet. Einzeltag-Anomalien sind peak und measurement_error",
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


def write_report(run_directory: Path) -> Path:
    raw_directory = run_directory / RAW_SUBDIR
    run_config = read_raw_json(run_directory, "run_config")
    e3_config = run_config["e3_config"]
    reference = e3_config["reference_system"]
    rule = e3_config["rule_system"]
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
        rule_system=rule,
        llm_system=llm,
        week_days=e3_config["week_days"],
    )
    tables = {
        "result_overview": (
            "Hauptkennzahlen, gepoolt über die Cutover",
            build_overview_table(summary.overall, reference=reference, rule=rule),
        ),
    }
    appendix = {
        "key_figures": (
            "Kennzahlen je Cutover",
            build_key_figures(summary, reference=reference, rule=rule, llm=llm),
        ),
        "result_forecast_weeks": (
            f"Tagesfehler je Woche ab der Dauerlast, Differenz gegen {reference}",
            build_week_table(
                summary.forecast_weeks, reference=reference, others=[rule, llm]
            ),
        ),
        "result_events": (
            "Erste Einordnung je Ereignis",
            build_event_table(summary.events, labels),
        ),
        "result_forecast": (
            f"Prognose ab Dauerlast und im Kontrolllauf, gepaart gegen {reference}",
            build_forecast_table(summary.forecast),
        ),
        "result_notifications": (
            "Meldungen nach der Erkennung der Dauerlast (Reihe Dauerlast ab Tag 0)",
            build_notification_table(summary.notifications),
        ),
        "result_control": (
            "Kontrolllauf: Fehlalarme und unnötige Resets",
            build_control_table(summary.control),
        ),
        "result_deviations": (
            f"Abweichungstage {rule} gegen {llm}",
            build_deviation_table(summary.deviations, labels, rule=rule, llm=llm),
        ),
        "result_criteria": (
            "Erkennung (TF1) und erste Einordnung (TF2) als Nebenzahlen, gepoolt über Cutover und Ereignisse",
            build_criteria_table(summary.criteria),
        ),
        "result_latency": (
            f"Laufzeit und Kosten {llm}, nur beschreibend",
            build_latency_table(summary.latency),
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
    write_explanation_rating_template(llm_outputs, output_directory)

    write_result_report(
        output_directory,
        title=f"E3 Dreiervergleich {reference}/{rule}/{llm}, Lauf {run_directory.name}",
        setup=build_setup(
            e3_config,
            run_config["standard_config"],
            run_config["llm_config"],
            labels,
            run_config["code_version"],
        ),
        tables=tables,
        notes=build_notes(summary),
        images=["e3_timeline.png"],
        decimals=STANDARD_CONFIG.decimals,
        appendix=appendix,
        appendix_text=[("Antworten des LLM", answer_lines(summary.answers, labels))],
    )

    return output_directory


def main() -> None:
    output_directory = write_report(
        run_directory_from_argv(PROJECT_CONFIG.e3_output_dir, RUN_PREFIX)
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
