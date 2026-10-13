# conda activate forecasting-env
# python -m experiments.e2_absence.e2_report [full|precheck] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_e2_absence import build_e2_plot
from experiments.common.harness import (
    read_anomaly_rows,
    read_calendar_availability,
    read_llm_outputs,
    read_structured_states,
)
from experiments.common.evaluation import ALL_EVENTS
from experiments.common.report import (
    KIND_LABELS,
    YES_NO,
    forecast_error_table,
    format_commit,
    format_cutovers,
    key_figures_table,
    write_explanation_rating_template,
    write_result_report,
)
from experiments.common.standard_config import (
    LLM_SYSTEM,
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    PROMPT_WINDOW_NUMBERS,
    RULE_SYSTEM,
    STANDARD_CONFIG,
)
from experiments.e2_absence.e2_config import (
    CLASSIFICATION_FILE,
    COMPARISON_FILE,
    PRECHECK_RUN_PREFIX,
    REDUCTION_FILE,
    RUN_PREFIX,
)
from experiments.e2_absence.e2_evaluation import (
    AnswerChecks,
    E2Summary,
    GatePrecheckSummary,
    FalseAlarms,
    RuleAgreement,
    summarize_answer_checks,
    summarize_classification,
    summarize_classification_rates,
    summarize_e2,
    summarize_false_alarms,
    summarize_gate_precheck,
    summarize_rule_agreement,
)
from experiments.e2_absence.e2_selection import (
    load_calendar_events,
    resolve_absence_window,
)
from src.config.config_forecasting import SYS_LABELS, TextCheckConfig
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
    "SYS3_CTX1_VISIT": "SYS3 mit Kalender, Gegenfall Besuch",
    "SYS3_CTX2": "SYS3 Kalender per Tool",
}

SERIES_LABELS = {
    ALL_EVENTS: "alle Reihen",
    "control": "Kontrolle",
    "scaled": "Sprung hoch",
    "scaled_down": "Sprung runter",
    "ramp_28": "Rampe hoch",
    "ramp_28_down": "Rampe runter",
    "peaks": "Spitzen",
    "stucks": "Festhänger",
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


def build_calendar_call_table(
    calendar_calls: pd.DataFrame, tool_configs: list[str]
) -> pd.DataFrame:
    calls = calendar_calls.loc[calendar_calls["config"].isin(tool_configs)]

    return pd.DataFrame(
        {
            "System": calls["config"],
            "nützlich": calls["useful"],
            "überflüssig": calls["superfluous"],
            "verpasst": calls["missed"],
            "zu Recht nicht abgerufen": calls["saved"],
        }
    )


def build_forecast_table(forecast: pd.DataFrame, reference: str) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "System": forecast["config"],
            "Phase": forecast["phase"].map(PHASE_LABELS),
        }
    ).join(forecast_error_table(forecast, "Tage", reference))
    table.insert(3, "Bias [W]", forecast["mean_day_bias_w"])

    return table


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
    standard_config: dict,
    summaries: dict[str, E2Summary],
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
    titles: dict[str, str],
    code_version: dict,
) -> dict[str, str]:
    counter_ids = e2_config["counter_event_ids"]
    setup = {
        f"Urlaub {event_id}": (
            f"{window_start.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d} bis vor {window_end.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d}, "
            f"Beginn = Tag 0, analysierte Tage {summaries[event_id].first_analyzed_day} bis {summaries[event_id].last_analyzed_day}, "
            + (
                f"Eintrag „{titles[event_id]}“, Gegenfall „{titles[counter_ids[event_id]]}“"
                if event_id in counter_ids
                else f"Eintrag „{titles[event_id]}“, ohne Gegenfall"
            )
        )
        for event_id, (window_start, window_end) in windows.items()
    }
    setup["Kanäle"] = (
        f"je Urlaub im Fenster aus Mains herausgerechnet, Coverage ab {e2_config['min_coverage_share_for_subtraction'] * 100:.0f} %"
    )
    for ctx, systems in e2_config["ctx_systems"].items():
        setup[f"Systeme {ctx}"] = ", ".join(systems)
    setup["Ereignisreihen"] = (
        f"{format_cutovers(standard_config, e2_config['event_cutovers'][standard_config['split']])}, ohne Kalender, Systeme {', '.join(e2_config['event_systems'])}: "
        + "; ".join(
            f"{SERIES_LABELS[series]} ("
            + (
                ", ".join(f"Tag {day}: {KIND_LABELS[kind]}" for day, kind in events)
                or "ohne Ereignis"
            )
            + ")"
            for series, events in e2_config["event_series"].items()
        )
    )
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


def build_classification_table(rates: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": rates["config"].map(SYS_LABELS),
            "erwartet": rates["expected"].replace(ALL_EVENTS, "alle Ereignisse"),
            "Ereignisse": rates["events"],
            "erkannt": rates["detected"],
            "richtig eingeordnet": [
                f"{correct}/{detected}"
                for correct, detected in zip(rates["correct"], rates["detected"])
            ],
            "richtig [%]": rates["correct_pct"],
        }
    )


def build_classification_event_table(events: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Reihe": events["series"].map(SERIES_LABELS),
            "Ereignis": [
                f"{number}: {KIND_LABELS[kind]}, Tag {day}"
                for number, kind, day in zip(
                    events["event"], events["kind"], events["start_day"]
                )
            ],
            "System": events["config"].map(SYS_LABELS),
            "erwartet": events["expected"],
            "bewertet an Tag": events["judged_day"],
            "Klasse": events["classification"],
            "Skala": events["trigger_scale"],
            "richtig": events["correct"].map(YES_NO),
        }
    )


def build_agreement_table(agreement: RuleAgreement) -> pd.DataFrame:
    summary = agreement.summary

    return pd.DataFrame(
        {
            "Cutover": summary["cutover_date"],
            "Reihe": summary["series"].map(SERIES_LABELS),
            "Tage": summary["days"],
            "Gate offen": summary["gate_open_days"],
            f"Tage mit anderer Klasse als {RULE_SYSTEM}": summary["deviation_days"],
            f"Meldungen {RULE_SYSTEM}": summary["rule_notification_days"],
            f"Meldungen {LLM_SYSTEM}": summary["llm_notification_days"],
        }
    )


def build_false_reset_table(alarms: FalseAlarms) -> pd.DataFrame:
    resets = alarms.resets

    return pd.DataFrame(
        {
            "Reihe": resets["series"].map(SERIES_LABELS),
            "Tage": resets["days"],
            f"Resets {RULE_SYSTEM}": resets["rule_reset_days"],
            f"Resets {LLM_SYSTEM}": resets["llm_reset_days"],
            f"falsche Resets {LLM_SYSTEM}": resets["false_reset_days"],
        }
    )


def build_outside_notification_table(alarms: FalseAlarms) -> pd.DataFrame:
    notifications = alarms.notifications

    return pd.DataFrame(
        {
            "System": notifications["config"].map(SYS_LABELS),
            "Reihe": notifications["series"].map(SERIES_LABELS),
            "Tage außerhalb der Ereignisse": notifications["days"],
            "Meldungen": notifications["notification_days"],
        }
    )


def build_deviation_table(deviations: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cutover": deviations["cutover_date"],
            "Reihe": deviations["series"].map(SERIES_LABELS),
            "Tag": deviations["days_since_cutover"],
            "Datum": deviations["analyzed_day"],
            f"Klasse {RULE_SYSTEM}": deviations["classification_rule"],
            f"Klasse {LLM_SYSTEM}": deviations["classification_llm"],
            f"Aktion {RULE_SYSTEM}": deviations["adaption_action_rule"],
            f"Aktion {LLM_SYSTEM}": deviations["adaption_action_llm"],
            "LLM-Ausfall": deviations["llm_failed"].map(YES_NO),
        }
    )


def build_event_deviation_table(deviations: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": deviations["config"],
            "Urlaubstag": deviations["days_since_cutover"],
            "Datum": deviations["analyzed_day"],
            f"Klasse {RULE_SYSTEM}": deviations["classification_rule"],
            "Klasse System": deviations["classification_llm"],
            f"Aktion {RULE_SYSTEM}": deviations["adaption_action_rule"],
            "Aktion System": deviations["adaption_action_llm"],
            "LLM-Ausfall": deviations["llm_failed"].map(YES_NO),
        }
    ).sort_values(["System", "Urlaubstag"])


def build_answer_check_table(
    checks: AnswerChecks, target_classification: str
) -> pd.DataFrame:
    summary = checks.summary

    return pd.DataFrame(
        {
            "Lauf": summary["scenario"],
            "System": summary["config"],
            "Antworten": summary["answers"],
            "Beleg fehlt": summary["unsupported_answers"],
            "Verstoß im Text": summary["violation_answers"],
            f"{target_classification}-Antworten": summary["target_answers"],
            "davon belegt": [
                f"{supported}/{answers}"
                for supported, answers in zip(
                    summary["target_supported_answers"], summary["target_answers"]
                )
            ],
        }
    )


def build_answer_findings_table(checks: AnswerChecks) -> pd.DataFrame:
    findings = checks.findings

    return pd.DataFrame(
        {
            "Lauf": findings["scenario"],
            "System": findings["config"],
            "Datum": findings["analyzed_day"],
            "Klasse": findings["classification"],
            "Verstoß im Text": findings["violations"],
            "fehlende Belege": findings["missing_evidence"],
        }
    )


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
            "davon nur eine Skala": phases["single_scale_gate_days"],
            "new_pattern": phases["new_pattern_days"],
            "low": phases["low_days"],
            "peak": phases["peak_days"],
            target_classification: phases["absence_classified_days"],
            "Resets": phases["reset_days"],
            "Meldungen": phases["notification_days"],
            "Ausfalltage": phases["failed_days"],
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
        }
    )


def summarize_event(
    raw_directory: Path,
    comparison: pd.DataFrame,
    reduction: pd.DataFrame,
    e2_config: dict,
    event_id: str,
    window: tuple[pd.Timestamp, pd.Timestamp],
) -> E2Summary:
    event_directory = raw_directory / event_id
    # Urlaube ohne Gegenfall haben keinen Ordner dafür
    ctxs = [ctx for ctx in e2_config["ctx_systems"] if (event_directory / ctx).exists()]

    return summarize_e2(
        comparison.loc[comparison["event_id"].eq(event_id)],
        read_ctx_anomaly(event_directory, ctxs),  # type: ignore
        pd.concat(
            [read_calendar_availability(event_directory / ctx) for ctx in ctxs],
            ignore_index=True,
        ),
        reduction.loc[reduction["event_id"].eq(event_id)],
        window_start=window[0],
        window_end=window[1],
        target_classification=e2_config["target_classification"],
        absence_event_id=event_id,
        counter_configs=list(
            e2_config["ctx_systems"].get(e2_config["counter_ctx"], {})
        ),
        reference_config=e2_config["reference_config"],
        context_reference_config=e2_config["context_reference_config"],
    )


def build_event_tables(
    summary: E2Summary, e2_config: dict, event_id: str
) -> dict[str, tuple[str, pd.DataFrame]]:
    target_classification = e2_config["target_classification"]
    context_reference = e2_config["context_reference_config"]
    # die Varianten mit Kalender, ctx0 ist die Referenz
    context_configs = [
        config
        for ctx, systems in e2_config["ctx_systems"].items()
        if ctx != "ctx0"
        for config in systems
    ]

    return {
        f"key_figures_{event_id}": (
            f"{event_id}: Kennzahlen",
            build_key_figures(summary, target_classification),
        ),
        f"result_phases_{event_id}": (
            f"{event_id}: Einordnung je Phase",
            build_phase_table(summary.phases, target_classification),
        ),
        f"result_absence_{event_id}": (
            f"{event_id}: Einordnung im Urlaub",
            build_absence_table(summary.absence_classification, target_classification),
        ),
        f"result_calendar_{event_id}": (
            f"{event_id}: Kalender im State",
            build_calendar_table(summary.calendar_use),
        ),
        f"result_calendar_calls_{event_id}": (
            f"{event_id}: Kalenderabruf per Tool, an Tagen mit Einordnung",
            build_calendar_call_table(
                summary.calendar_calls, list(e2_config["ctx_systems"]["ctx2"])
            ),
        ),
        f"result_forecast_{event_id}": (
            f"{event_id}: Prognose je Phase, gepaart gegen {e2_config['reference_config']}",
            build_forecast_table(summary.forecast, e2_config["reference_config"]),
        ),
        f"result_forecast_context_{event_id}": (
            f"{event_id}: Prognose je Phase der Varianten mit Kalender, gepaart gegen {context_reference}",
            build_forecast_table(
                summary.context_forecast.loc[
                    summary.context_forecast["config"].isin(context_configs)
                ],
                context_reference,
            ),
        ),
        f"result_deviations_{event_id}": (
            f"{event_id}: Tage mit anderer Klasse als {RULE_SYSTEM}",
            build_event_deviation_table(summary.deviations),
        ),
    }


def write_full_report(run_directory: Path) -> None:
    run_config = read_raw_json(run_directory, "run_config")
    e2_config = run_config["e2_config"]
    target_classification = e2_config["target_classification"]

    calendar_events = load_calendar_events(Path(e2_config["calendar_events_file"]))
    windows = {
        event_id: resolve_absence_window(calendar_events, event_id)
        for event_id in e2_config["absence_event_ids"]
    }

    raw_directory = run_directory / RAW_SUBDIR
    comparison = pd.read_csv(
        raw_directory / f"{COMPARISON_FILE}.csv", parse_dates=["decision_time"]
    )
    reduction = pd.read_csv(raw_directory / f"{REDUCTION_FILE}.csv")
    summaries = {
        event_id: summarize_event(
            raw_directory, comparison, reduction, e2_config, event_id, window
        )
        for event_id, window in windows.items()
    }

    series_days = pd.read_csv(
        raw_directory / f"{CLASSIFICATION_FILE}.csv", dtype={"cutover_date": str}
    )
    classification = summarize_classification(series_days, e2_config["event_series"])
    agreement = summarize_rule_agreement(
        series_days, rule_system=RULE_SYSTEM, llm_system=LLM_SYSTEM
    )
    alarms = summarize_false_alarms(
        series_days,
        e2_config["event_series"],
        rule_system=RULE_SYSTEM,
        llm_system=LLM_SYSTEM,
    )
    text_check_config = TextCheckConfig()
    llm_outputs = read_llm_outputs(raw_directory)
    checks = summarize_answer_checks(
        llm_outputs,
        read_structured_states(raw_directory),
        target_classification=target_classification,
        control_words=text_check_config.control_words,
        number_tolerance=text_check_config.number_tolerance,
        rounding_step=text_check_config.rounding_step,
        prompt_numbers=PROMPT_WINDOW_NUMBERS,
    )

    output_directory = user_output_directory(run_directory)
    tables: dict[str, tuple[str, pd.DataFrame]] = {
        "result_classification": (
            "Einordnung auf den Ereignisreihen: richtige Klasse am Bewertungstag",
            build_classification_table(summarize_classification_rates(classification)),
        ),
        "result_false_resets": (
            f"Falsche Resets von {LLM_SYSTEM}: Reset, den {RULE_SYSTEM} am selben Tag nicht macht, in Reihen ohne Dauerlast",
            build_false_reset_table(alarms),
        ),
        "result_classification_events": (
            "Einordnung je Ereignis",
            build_classification_event_table(classification),
        ),
        "result_agreement": (
            f"Ereignisreihen: Übereinstimmung von {LLM_SYSTEM} mit der Regel {RULE_SYSTEM}, auch ohne Ereignis",
            build_agreement_table(agreement),
        ),
        "result_outside_notifications": (
            "Ereignisreihen: Meldungen außerhalb der Ereignisse",
            build_outside_notification_table(alarms),
        ),
        "result_answer_checks": (
            "Belege und Text der LLM-Antworten",
            build_answer_check_table(checks, target_classification),
        ),
    }
    appendix: dict[str, tuple[str, pd.DataFrame]] = {
        "result_deviations": (
            f"Ereignisreihen: Tage, an denen {LLM_SYSTEM} anders einordnet als {RULE_SYSTEM}",
            build_deviation_table(agreement.deviations),
        ),
        "result_answer_findings": (
            "Antworten mit fehlendem Beleg oder Verstoß im Text",
            build_answer_findings_table(checks),
        ),
    }
    for event_id, summary in summaries.items():
        build_e2_plot(
            summary.timeline,
            output_directory,
            configs=tuple(e2_config["plot_configs"]),
            config_labels=CONFIG_LABELS,
            name=f"e2_timeline_{event_id}",
        )
        tables.update(build_event_tables(summary, e2_config, event_id))
        appendix[f"result_reduction_{event_id}"] = (
            f"{event_id}: Absenkung je Tag im Urlaubsfenster",
            build_reduction_table(summary.reduction),
        )

    write_result_report(
        output_directory,
        title=f"E2 Abwesenheit, Lauf {run_directory.name}",
        setup=build_setup(
            e2_config,
            run_config["standard_config"],
            summaries,
            windows,
            {str(event["event_id"]): str(event["title"]) for event in calendar_events},
            run_config["code_version"],
        ),
        tables=tables,
        notes=[
            "Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag",
            "Ereignisreihen: richtig = die Klasse am Bewertungstag ist die erwartete (peak, new_pattern, measurement_error). Bewertet wird bei Spitze und Festhänger am Tag nach dem Ereignis, wenn das Gate offen ist, beim Sprung am ersten Tag mit anhaltender Abweichung oder new_pattern. Kein Bewertungstag = nicht erkannt",
            "richtig [%]: Anteil unter den erkannten Ereignissen. Die Regel (SYS2) und SYS1 sind der Maßstab für das LLM (SYS3), SYS1 handelt nie",
            "Nach dem ersten Festhänger schließen SYS2 und SYS3 den Tag aus der Referenz aus, SYS1 nicht. Festhänger 2 und 3 werden daher mit verschiedenem Zustand eingeordnet. Bei den Spitzen gibt es keine Handlung, dort laufen alle Systeme gleich",
            f"Treffer = {target_classification} mit passendem Kalendereintrag. {target_classification} ohne Beleg (ohne Kalender, "
            "Kalender nicht abgerufen oder nach der Rückkehr) zählt als Fehlklassifikation, über alle Phasen",
            "Treffer: von den Urlaubstagen mit offenem Gate, an den übrigen wird nicht eingeordnet. Wenige Tage, deshalb als Anzahl",
            f"Einordnung je Phase: {target_classification} ist keine Meldung, im Urlaub ist jede Meldung ein Fehlalarm. Ausfalltage = LLM ohne gültige Antwort",
            "Gate offen: Einzeltag, Drift (weekly und long_term halten an) oder nur eine anhaltende Skala",
            "Prognose je Phase: Phase und Fehler nach dem Prognosetag. Tagesfehler (Hauptmaß) = Betrag von Prognose-Tagesmittel minus Ist-Tagesmittel, "
            "gemittelt über die Tage. Bias = dasselbe mit Vorzeichen, negativ = Prognose zu niedrig. MAE = mittlerer Stundenfehler",
            f"Differenzen gegen {e2_config['reference_config']} bzw. gegen {e2_config['context_reference_config']} (Tabellen mit Kalender): gepaart am selben Prognosetag, negativ = besser",
            f"Prognosephase nach der Rückkehr: {e2_config['decision_time_margin_after_days']} Tage, so lange dauert es, bis die Urlaubstage aus dem Trainingsfenster von Prophet herausgerollt sind",
            f"Falsche Resets: Reihen ohne Dauerlast sind Kontrolle, Spitzen und Festhänger, dort verlangt kein Ereignis einen Reset. Falsch = {LLM_SYSTEM} setzt an einem Tag zurück, an dem {RULE_SYSTEM} es nicht tut. Resets von {RULE_SYSTEM} stehen daneben, zählen aber nicht als falsch. SYS1 handelt nie. Summe über alle Cutover, ab dem ersten Unterschied sehen die Systeme verschiedene Zustände",
            "Meldungen außerhalb der Ereignisse: Tage ohne Ereignis, bei Spitze und Festhänger ohne den ersten Einordnungstag, beim Sprung und der Rampe vor dem ersten Einordnungstag, in der Kontrolle alle. Meldung = peak, new_pattern oder measurement_error, Summe über alle Cutover",
            f"Ereignisreihen ohne Kalender, Kontrolle = unveränderte Daten ohne Ereignis, zählt nicht in die Quote. Tage mit anderer Klasse als {RULE_SYSTEM}: ab der ersten Abweichung sehen die Systeme verschiedene Zustände, spätere Unterschiede können Folgen sein",
            "Belege: Beleg fehlt = zur Klasse fehlt ein Pfad (peak und low die Richtung, new_pattern die Streaks der anhaltenden Skalen, measurement_error das Flag, absence ein Kalendereintrag, der im State steht). Verstoß im Text = Steuerung, Preis oder Tarif, Zahl oder Uhrzeit, die nicht im State steht",
            "Die Belegprüfung sagt nichts über die Wahrheit des Textes, Passung zur Klasse bewerten Personen (explanation_ratings_template.csv)",
            "ctx0 ohne, ctx1 mit Kalender im State, ctx2 Kalender per Tool. SYS1 und SYS2 lesen keinen Kalender und laufen nur in ctx0",
            f"Kalendereinträge als Freitext aus calendar_events.json, im Gegenfall {e2_config['counter_ctx']} steht zu denselben Zeiten nur "
            f"ein Eintrag, der keine Abwesenheit meint. Dort ist jedes {target_classification} falsch und zählt als {target_classification} ohne Beleg",
            "Kalender im State: bei ctx2 hat das LLM an diesen Tagen nachgeschaut, jeder ctx2-Tag mit LLM kostet einen zusätzlichen Aufruf für die Tool-Entscheidung",
            "Kalenderabruf: nützlich = abgerufen an einem Urlaubstag (ein Eintrag deckt den Tag), überflüssig = abgerufen ohne deckenden Eintrag, "
            "verpasst = nicht abgerufen an einem Urlaubstag. Vergleich: ctx1 schaut immer nach",
        ],
        images=[f"e2_timeline_{event_id}.png" for event_id in summaries],
        decimals=STANDARD_CONFIG.decimals,
        appendix=appendix,
    )
    write_explanation_rating_template(llm_outputs, output_directory)

    print(f"Result written to {output_directory / 'ergebnis.md'}")


def write_precheck_report(run_directory: Path) -> None:
    run_config = read_raw_json(run_directory, "run_config")
    e2_config = run_config["e2_config"]
    target_classification = e2_config["target_classification"]

    calendar_events = load_calendar_events(Path(e2_config["calendar_events_file"]))
    raw_directory = run_directory / RAW_SUBDIR
    comparison = pd.read_csv(raw_directory / f"{COMPARISON_FILE}.csv")

    setup: dict[str, str] = {}
    tables: dict[str, tuple[str, pd.DataFrame]] = {}
    appendix: dict[str, tuple[str, pd.DataFrame]] = {}
    for event_id in e2_config["absence_event_ids"]:
        window_start, window_end = resolve_absence_window(calendar_events, event_id)
        summary = summarize_gate_precheck(
            comparison.loc[comparison["event_id"].eq(event_id)],
            read_ctx_anomaly(raw_directory / event_id, e2_config["ctx_systems"]),
            window_start=window_start,
            window_end=window_end,
            target_classification=target_classification,
            absence_event_id=event_id,
            counter_configs=[],
        )
        setup[f"Urlaub {event_id}"] = (
            f"{window_start.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d} bis vor {window_end.tz_convert(LOCAL_TIMEZONE):%Y-%m-%d}"
        )
        tables[f"precheck_first_days_{event_id}"] = (
            f"{event_id}: Erste Tage ab Urlaubsbeginn",
            build_precheck_first_days_table(summary),
        )
        tables[f"precheck_phases_{event_id}"] = (
            f"{event_id}: Gate und Einordnung je Phase",
            build_phase_table(summary.phases, target_classification),
        )
        appendix[f"precheck_days_{event_id}"] = (
            f"{event_id}: Je Tag ab Urlaubsbeginn",
            build_precheck_days_table(summary),
        )

    setup["Systeme"] = ", ".join(e2_config["ctx_systems"]["ctx0"])
    setup["Tage nach der Rückkehr"] = str(e2_config["decision_time_margin_after_days"])
    setup["Commit"] = format_commit(run_config["code_version"])

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"E2 Vorprüfung Gate, Lauf {run_directory.name}",
        setup=setup,
        tables=tables,
        notes=[
            "Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag",
            "Gate offen: Einzeltag (daily/weekday über ihrer Schwelle), Drift (weekly und long_term halten an) oder nur eine anhaltende Skala",
            "Reset = new_pattern mit advance_history_start, bei SYS1 nie",
        ],
        images=[],
        decimals=STANDARD_CONFIG.decimals,
        appendix=appendix,
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
