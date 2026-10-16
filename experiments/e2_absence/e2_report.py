# conda activate forecasting-env
# python -m experiments.e2_absence.e2_report [full|precheck] [run_directory]

import sys
from pathlib import Path

import pandas as pd

from docs.plots.plot_e2_absence import build_e2_return_plot
from experiments.common.harness import (
    read_anomaly_rows,
    read_calendar_availability,
    read_llm_outputs,
    read_structured_states,
)
from experiments.common.evaluation import ALL_EVENTS
from experiments.common.report import (
    KIND_LABELS,
    NOISE_RULE_NOTE,
    YES_NO,
    criteria_table,
    build_setup,
    format_commit,
    format_count,
    format_difference,
    format_difference_range,
    format_number,
    stichtag_labels,
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
    CHANNEL_RANKING_FILE,
    CLASSIFICATION_FILE,
    COMPARISON_FILE,
    PRECHECK_RUN_PREFIX,
    REDUCTION_FILE,
    RETURN_CONTEXT_PLOT_FILE,
    RETURN_PLOT_FILE,
    RUN_PREFIX,
    E2Config,
)
from experiments.e2_absence.e2_evaluation import (
    E2Summary,
    GatePrecheckSummary,
    count_failed_days,
    summarize_absence_overview,
    summarize_agreement_by_series,
    summarize_answer_checks,
    summarize_answer_overview,
    summarize_calendar_call_totals,
    summarize_classification,
    summarize_classification_comparison,
    summarize_deviation_classes,
    summarize_e2,
    summarize_gate_precheck,
    summarize_phase_overview,
    summarize_return_forecast,
    summarize_return_curve,
    summarize_rule_agreement,
    summarize_tf2_criteria,
    total_absence_by_variant,
)
from experiments.e2_absence.e2_selection import (
    load_calendar_events,
    resolve_absence_window,
)
from src.config.config_forecasting import TextCheckConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

CONFIG_LABELS = {
    "SYS1": "SYS1",
    "SYS2": "SYS2",
    "SYS3_CTX0": "SYS3 CTX0",
    "SYS3_CTX1": "SYS3 CTX1",
    "SYS3_CTX1_VISIT": "Gegenfall CTX1",
    "SYS3_CTX2": "SYS3 CTX2",
}
CONTEXT_CONFIG = "SYS3_CTX1"
ABSENCE_CONFIGS = ("SYS2", "SYS3_CTX0", "SYS3_CTX1", "SYS3_CTX2", "SYS3_CTX1_VISIT")
PHASE_CONFIGS = ("SYS1",) + ABSENCE_CONFIGS

PHASE_LABELS = {
    "before": "vor dem Urlaub",
    "absence": "Urlaub",
    "after_return": "nach der Rückkehr",
}

EXAMPLE_ANSWERS = (
    ("event-2016-11/ctx1", "absence", "2016-12-02"),
    ("event-2016-12/ctx1_visit", "absence", None),
    ("event-2016-11/ctx0", "low", None),
    ("peaks_2017-02-20", "peak", "2017-02-20"),
    ("scaled_2017-01-13", "new_pattern", None),
    ("stucks_2016-12-02", "measurement_error", None),
)


def series_labels(event_series: dict[str, list]) -> dict[str, str]:
    labels = {ALL_EVENTS: "alle", "control": KIND_LABELS["control"]}
    for series, events in event_series.items():
        if len(events) == 1:
            labels[series] = KIND_LABELS[events[0][1]]
        elif events:
            labels[series] = series

    return labels


def absence_labels(
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
) -> dict[str, str]:
    labels = {ALL_EVENTS: "alle"}
    for number, event_id in enumerate(
        sorted(windows, key=lambda event: windows[event][0]), start=1
    ):
        labels[event_id] = f"Urlaub {number}"

    return labels


def format_window(window: tuple[pd.Timestamp, pd.Timestamp]) -> str:
    start, end = window
    last_day = end.tz_convert(LOCAL_TIMEZONE) - pd.Timedelta(days=1)
    return f"{start.tz_convert(LOCAL_TIMEZONE):%d.%m.}–{last_day:%d.%m.%Y}"


def read_ctx_anomaly(raw_directory: Path, ctx_systems: dict) -> pd.DataFrame:
    return pd.concat(
        [read_anomaly_rows(raw_directory / ctx) for ctx in ctx_systems],
        ignore_index=True,
    )


def build_tf2_criteria(criteria: pd.DataFrame) -> pd.DataFrame:
    rows = {row["criterion"]: row for row in criteria.to_dict("records")}
    correct = rows["correct"]
    hits = rows["hits"]
    without_entry = rows["absence_without_entry"]
    evidence = rows["missing_evidence"]

    return criteria_table(
        [
            (
                "richtig eingeordnete Ereignisse",
                "≥ 80 %",
                format_count(correct["value"], correct["total"], correct["share_pct"]),
                correct["fulfilled"],
            ),
            (
                "Treffer je Abwesenheit",
                "> 0 Urlaubstage",
                f"{hits['value']} Urlaubstage",
                hits["fulfilled"],
            ),
            (
                "absence ohne passenden Eintrag",
                "0 Tage",
                f"{without_entry['value']} Tage",
                without_entry["fulfilled"],
            ),
            (
                "fehlende Belege",
                "0 Antworten",
                format_count(
                    evidence["value"], evidence["total"], evidence["share_pct"]
                ),
                evidence["fulfilled"],
            ),
        ]
    )


def build_tf3_criterion(
    return_forecast: pd.DataFrame, labels: dict[str, str], reference: str
) -> pd.DataFrame:
    return criteria_table(
        [
            (
                f"Tagesfehler {CONFIG_LABELS[CONTEXT_CONFIG]} minus {reference} nach der Rückkehr, {labels[row['event_id']]}",
                "< 0, belastbar",
                format_difference(
                    row["reference_mean_delta"],
                    2 * row["reference_delta_standard_error"],
                    bool(row["reference_exceeds_noise"]),
                    STANDARD_CONFIG.decimals,
                ),
                bool(row["reference_exceeds_noise"])
                and row["reference_mean_delta"] < 0,
            )
            for row in return_forecast.to_dict("records")
        ]
    )


def build_classification_table(comparison: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "erwartete Klasse": comparison["expected"].replace(ALL_EVENTS, "alle"),
            "Ereignisse": comparison["events"],
            f"{LLM_SYSTEM} richtig": [
                f"{correct} von {detected}"
                for correct, detected in zip(
                    comparison["llm_correct"], comparison["llm_detected"]
                )
            ],
            f"{RULE_SYSTEM} richtig": [
                f"{correct} von {detected}"
                for correct, detected in zip(
                    comparison["rule_correct"], comparison["rule_detected"]
                )
            ],
            f"new_pattern, eine Skala ({LLM_SYSTEM})": comparison[
                "llm_single_scale"
            ].astype("Int64"),
        }
    )


def build_absence_table(totals: pd.DataFrame) -> pd.DataFrame:
    rows = {row["config"]: row for row in totals.to_dict("records")}

    return pd.DataFrame(
        {
            "Variante": [CONFIG_LABELS[config] for config in ABSENCE_CONFIGS],
            "absence": [
                format_count(rows[config]["absence_events"], rows[config]["events"])
                for config in ABSENCE_CONFIGS
            ],
            "absence-Tage": [
                format_count(
                    rows[config]["absence_days"], rows[config]["gate_open_days"]
                )
                for config in ABSENCE_CONFIGS
            ],
            "absence ohne Eintrag": [
                int(rows[config]["unsupported_absence_days"])
                for config in ABSENCE_CONFIGS
            ],
            "Zurücksetzen im Urlaub": [
                int(rows[config]["reset_days"]) for config in ABSENCE_CONFIGS
            ],
        }
    )


def build_return_table(
    return_forecast: pd.DataFrame,
    labels: dict[str, str],
    reference: str,
    context_reference: str,
) -> pd.DataFrame:
    decimals = STANDARD_CONFIG.decimals

    def difference(mean: pd.Series, standard_error: pd.Series) -> list[str]:
        return [
            format_difference_range(value, 2 * error, decimals)
            for value, error in zip(mean, standard_error)
        ]

    return pd.DataFrame(
        {
            "Urlaub": return_forecast["event_id"].map(labels),
            f"Differenz zu {reference} [W]": difference(
                return_forecast["reference_mean_delta"],
                return_forecast["reference_delta_standard_error"],
            ),
            f"belastbar zu {reference}": return_forecast["reference_exceeds_noise"].map(
                YES_NO
            ),
            f"Differenz zu {CONFIG_LABELS[context_reference]} [W]": difference(
                return_forecast["context_mean_delta"],
                return_forecast["context_delta_standard_error"],
            ),
            f"belastbar zu {CONFIG_LABELS[context_reference]}": return_forecast[
                "context_exceeds_noise"
            ].map(YES_NO),
        }
    )


def build_calendar_call_table(
    calls: pd.DataFrame, labels: dict[str, str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Urlaub": calls["event_id"].map(labels),
            "abgerufen, Urlaubstag": calls["useful"].astype("Int64"),
            "abgerufen, anderer Tag": calls["superfluous"].astype("Int64"),
            "nicht abgerufen, Urlaubstag": calls["missed"].astype("Int64"),
            "nicht abgerufen, anderer Tag": calls["saved"].astype("Int64"),
        }
    )


def build_answer_overview_table(
    overview: pd.DataFrame, target_classification: str
) -> pd.DataFrame:
    row = overview.iloc[0]

    return pd.DataFrame(
        {
            "Kennzahl": [
                "Antworten",
                "Beleg fehlt",
                "Verstoß im Text",
                "davon Zahl, die nicht im Zustand steht",
                "davon Wort zu Steuerung, Preis oder Tarif",
                f"{target_classification}-Antworten belegt",
            ],
            "Wert": [
                str(row["answers"]),
                f"{row['unsupported_answers']} (Klasse {row['unsupported_classes']}, fehlt {row['missing_paths']})",
                str(row["violation_answers"]),
                str(row["number_answers"]),
                str(row["control_answers"]),
                format_count(row["target_supported_answers"], row["target_answers"]),
            ],
        }
    )


def build_deviation_class_table(classes: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            f"Klasse {RULE_SYSTEM}": classes["classification_rule"],
            f"Klasse {LLM_SYSTEM}": classes["classification_llm"],
            "Tage": classes["days"],
        }
    )


def build_phase_overview_table(
    phases: pd.DataFrame, labels: dict[str, str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Urlaub": phases["event_id"].map(labels),
            "Variante": phases["config"].map(CONFIG_LABELS),
            "Vorfilter offen": phases["gate_open_days"],
            "low": phases["low_days"],
            "absence": phases["absence_days"],
            "Zurücksetzen U / R": [
                f"{during} / {after}"
                for during, after in zip(
                    phases["reset_days"], phases["reset_days_after"]
                )
            ],
            "Meldungstage U / R": [
                f"{during} / {after}"
                for during, after in zip(
                    phases["notification_days"], phases["notification_days_after"]
                )
            ],
            "Tagesfehler U [W]": phases["day_error_absence"],
            "Tagesfehler R [W]": phases["day_error_after_return"],
            "Bias U [W]": phases["bias_absence"],
            "Bias R [W]": phases["bias_after_return"],
        }
    )


def read_subtracted_appliances(event_ids: list[str]) -> list[str]:
    appliances: dict[str, None] = {}
    for event_id in event_ids:
        ranking = pd.read_csv(
            PROJECT_CONFIG.e2_output_dir
            / E2Config().channel_selection_subdir(event_id)
            / f"{CHANNEL_RANKING_FILE}.csv"
        )
        appliances |= dict.fromkeys(ranking.loc[ranking["is_selected"], "appliance"])

    return list(appliances)


def build_phase_table(phases: pd.DataFrame, target_classification: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Systemvariante": phases["config"].map(CONFIG_LABELS),
            "Phase": phases["phase"].map(PHASE_LABELS),
            "Tage": phases["days"],
            "Vorfilter offen": phases["gate_open_days"],
            "davon Einzelanomalie": phases["alarm_days"],
            "davon anhaltende Veränderung": phases["drift_gate_days"],
            "davon nur eine Skala": phases["single_scale_gate_days"],
            "new_pattern": phases["new_pattern_days"],
            "low": phases["low_days"],
            "peak": phases["peak_days"],
            target_classification: phases["absence_classified_days"],
            "Zurücksetzen": phases["reset_days"],
            "Meldungstage": phases["notification_days"],
            "Ausfalltage": phases["failed_days"],
        }
    )


def format_event_cell(row: dict | None) -> str:
    if row is None or pd.isna(row["judged_day"]):
        return "-"
    text = f"{int(row['judged_day'])} ({row['trigger_scale']})"
    return text if row["correct"] else f"{text}, {row['classification']}"


def build_classification_event_table(
    events: pd.DataFrame, systems: list[str], stichtage: dict[str, str]
) -> pd.DataFrame:
    keys = ["cutover_date", "series", "start_day"]
    cells = {
        (*(row[key] for key in keys), row["config"]): row
        for row in events.to_dict("records")
    }
    rows = (
        events.drop_duplicates(keys).sort_values(keys, kind="stable").to_dict("records")
    )

    return pd.DataFrame(
        {
            "Stichtag": [stichtage[row["cutover_date"]] for row in rows],
            "Ereignis": [
                f"{KIND_LABELS[row['kind']]}, Tag {row['start_day']}" for row in rows
            ],
            "erwartet": [row["expected"] for row in rows],
        }
        | {
            system: [
                format_event_cell(cells.get((*(row[key] for key in keys), system)))
                for row in rows
            ]
            for system in systems
        }
    )


def build_agreement_table(
    agreement: pd.DataFrame, labels: dict[str, str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Reihe": agreement["series"].map(labels),
            "Tage": agreement["days"],
            "Vorfilter offen": agreement["gate_open_days"],
            "andere Klasse": agreement["deviation_days"],
            f"Meldungstage {RULE_SYSTEM}": agreement["rule_notification_days"],
            f"Meldungstage {LLM_SYSTEM}": agreement["llm_notification_days"],
        }
    )


def build_violation_table(findings: pd.DataFrame) -> pd.DataFrame:
    violations = findings.loc[findings["violations"].ne("")]

    return pd.DataFrame(
        {
            "Lauf": violations["scenario"],
            "System": violations["config"].replace(CONFIG_LABELS),
            "Datum": violations["analyzed_day"],
            "Klasse": violations["classification"],
            "Verstoß": violations["violations"],
        }
    )


def example_answer_lines(llm_outputs: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for scenario, classification, analyzed_day in EXAMPLE_ANSWERS:
        candidates = llm_outputs.loc[
            llm_outputs["scenario"].eq(scenario)
            & llm_outputs["classification"].eq(classification)
        ].sort_values("analyzed_day")
        if analyzed_day is not None:
            candidates = candidates.loc[candidates["analyzed_day"].eq(analyzed_day)]
        if candidates.empty:
            continue
        answer = candidates.iloc[0]
        lines += [
            f"**{answer['scenario']}, eingeordneter Tag {answer['analyzed_day']}, Klasse {answer['classification']}**",
            "",
            f"- Erklärung: {answer['explanation']}",
            f"- Empfehlung: {answer['user_recommendation']}",
            f"- Unsicherheit: {answer['uncertainty']}",
            f"- Belege: {str(answer['evidence_paths']).replace(';', ', ')}",
            "",
        ]

    return lines


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


def describe_series(series: str, events: list, labels: dict[str, str]) -> str:
    if not events:
        return labels[series]
    days = ", ".join(str(day) for day, _ in events)
    text = f"{events[0][1]} an Tag {days}"
    return text if labels[series] == events[0][1] else f"{series} = {text}"


def build_study_setup(
    e2_config: dict,
    standard_config: dict,
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
    labels: dict[str, str],
    titles: dict[str, str],
    events_labels: dict[str, str],
    mean_reductions: dict[str, float],
    errors_before: dict[str, float],
    appliances: list[str],
    run_name: str,
    code_version: dict,
) -> dict[str, str]:
    counter_ids = e2_config["counter_event_ids"]
    decimals = STANDARD_CONFIG.decimals
    details = {}
    for event_id in sorted(windows, key=lambda event: windows[event][0]):
        details[labels[event_id]] = (
            f"{format_window(windows[event_id])}, Eintrag „{titles[event_id]}“"
            + (
                f", Gegenfall „{titles[counter_ids[event_id]]}“"
                if event_id in counter_ids
                else ""
            )
            + f", Absenkung im Mittel {format_number(mean_reductions[event_id], decimals)} W"
            + f", Tagesfehler vor dem Urlaub {format_number(errors_before[event_id], decimals)} W"
        )
    details["Prognosefenster"] = (
        f"{e2_config['decision_time_margin_before_days']} Tage vor und {e2_config['decision_time_margin_after_days']} Tage nach jedem Urlaub"
    )
    details["Abgezogene Gerätekanäle"] = (
        f"Abdeckung ab {e2_config['min_coverage_share_for_subtraction'] * 100:.0f} %, "
        + "; ".join(appliances)
    )

    return build_setup(
        run_name,
        standard_config,
        e2_config["event_cutovers"][standard_config["split"]],
        code_version,
        scenarios="Ereignisreihen ohne Kalender: "
        + "; ".join(
            describe_series(series, events, events_labels)
            for series, events in e2_config["event_series"].items()
        )
        + ", dazu die Urlaube",
        systems="Ereignisreihen "
        + ", ".join(e2_config["event_systems"])
        + "; Urlaube "
        + ", ".join(
            CONFIG_LABELS[config]
            for systems in e2_config["ctx_systems"].values()
            for config in systems
        ),
        details=details,
    )


NOTES = [
    "Ereignisreihen: richtig = die erwartete Klasse am Bewertungstag. Bewertet wird bei peak und stuck am Tag nach dem Ereignis (Vorfilter offen), bei Dauerlast und Rampe am ersten Tag mit anhaltender Veränderung oder new_pattern. Ohne Bewertungstag zählt das Ereignis nicht in die Quote",
    "new_pattern, eine Skala: new_pattern, obwohl laut Zustand nur weekly oder long_term anhält. Am Goldstandard zählt es als richtig",
    "absence = Urlaube, in denen absence eingeordnet wurde, absence-Tage von den Urlaubstagen mit offenem Vorfilter. Ein Treffer ist absence mit passendem Kalendereintrag. absence ohne passenden Eintrag (ohne Kalender, im Gegenfall, nach der Rückkehr) zählt als Fehlklassifikation, im Gegenfall meint der Eintrag keine Abwesenheit",
    "Urlaubstage mit offenem Vorfilter unterscheiden sich je Variante, nach einem Zurücksetzen im Urlaub fehlen Skalen und der Vorfilter bleibt zu",
    "Kalenderabruf (CTX2): nützlich = abgerufen an Urlaubstagen, überflüssig = an anderen Tagen. CTX1 hat den Kalender immer im Zustand",
    "Tagesfehler = mittlerer Betrag von Prognose- minus gemessenem Tagesmittel, Bias dasselbe mit Vorzeichen (negativ = Prognose zu niedrig). Differenzen gepaart am Prognosetag, negativ = besser. Nach der Rückkehr dauert, bis die Urlaubstage aus dem Trainingsfenster gerollt sind",
    NOISE_RULE_NOTE,
    "fehlende Belege: zur vergebenen Klasse fehlt ein Pfad im Zustand (peak und low die Richtung, new_pattern die anhaltenden Skalen, measurement_error die Plausibilität, absence ein Kalendereintrag). Verstoß im Text: eine Zahl oder ein Wort zu Steuerung, Preis oder Tarif, das nicht im Zustand steht. Die Prüfung sagt nichts darüber, ob der Text stimmt",
    "Ab der ersten abweichenden Aktion sehen die Varianten verschiedene Zustände, spätere Unterschiede können Folgen davon sein",
]


def write_full_report(run_directory: Path) -> None:
    run_config = read_raw_json(run_directory, "run_config")
    e2_config = run_config["e2_config"]
    standard_config = run_config["standard_config"]
    target_classification = e2_config["target_classification"]
    reference = e2_config["reference_config"]
    context_reference = e2_config["context_reference_config"]
    stichtage = stichtag_labels(standard_config)
    events_labels = series_labels(e2_config["event_series"])

    calendar_events = load_calendar_events(E2Config().calendar_events_file)
    windows = {
        event_id: resolve_absence_window(calendar_events, event_id)
        for event_id in e2_config["absence_event_ids"]
    }
    labels = absence_labels(windows)

    raw_directory = run_directory / RAW_SUBDIR
    comparison = pd.read_csv(
        raw_directory / f"{COMPARISON_FILE}.csv", parse_dates=["decision_time"]
    )
    reduction = pd.read_csv(raw_directory / f"{REDUCTION_FILE}.csv")
    summaries = {
        event_id: summarize_event(
            raw_directory, comparison, reduction, e2_config, event_id, window
        )
        for event_id, window in sorted(windows.items(), key=lambda item: item[1][0])
    }

    series_days = pd.read_csv(
        raw_directory / f"{CLASSIFICATION_FILE}.csv", dtype={"cutover_date": str}
    )
    classification = summarize_classification(series_days, e2_config["event_series"])
    classification_comparison = summarize_classification_comparison(
        classification, rule_system=RULE_SYSTEM, llm_system=LLM_SYSTEM
    )
    agreement = summarize_rule_agreement(
        series_days, rule_system=RULE_SYSTEM, llm_system=LLM_SYSTEM
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
    phases = summarize_phase_overview(summaries, PHASE_CONFIGS)
    absence = summarize_absence_overview(summaries, ABSENCE_CONFIGS)
    return_forecast = summarize_return_forecast(summaries, CONTEXT_CONFIG)
    failed_days = count_failed_days(summaries)

    output_directory = user_output_directory(run_directory)
    tables: dict[str, tuple[str, pd.DataFrame]] = {
        "result_criteria": (
            "Kriterien der Teilfrage 2",
            build_tf2_criteria(
                summarize_tf2_criteria(
                    classification_comparison,
                    absence,
                    checks.summary,
                    context_config=CONTEXT_CONFIG,
                )
            ),
        ),
        "result_criteria_tf3": (
            "Kriterium der Teilfrage 3 aus E2: Tagesfehler nach der Rückkehr",
            build_tf3_criterion(return_forecast, labels, reference),
        ),
        "result_classification": (
            "Richtig eingeordnete Ereignisse je erwarteter Klasse, ohne Kalender",
            build_classification_table(classification_comparison),
        ),
        "result_absence": (
            "Einordnung als absence je Variante",
            build_absence_table(total_absence_by_variant(absence)),
        ),
        "result_return_forecast": (
            f"Tagesfehler nach der Rückkehr, {CONFIG_LABELS[CONTEXT_CONFIG]} gegen {reference} und gegen {CONFIG_LABELS[context_reference]}",
            build_return_table(return_forecast, labels, reference, context_reference),
        ),
        "result_calendar_calls": (
            f"Kalenderabruf bei {CONFIG_LABELS['SYS3_CTX2']}, an Tagen mit Einordnung",
            build_calendar_call_table(
                summarize_calendar_call_totals(
                    summaries, list(e2_config["ctx_systems"]["ctx2"])
                ),
                labels,
            ),
        ),
        "result_answer_overview": (
            "Belegprüfung der Antworten",
            build_answer_overview_table(
                summarize_answer_overview(checks.summary, checks.findings),
                target_classification,
            ),
        ),
        "result_deviation_classes": (
            f"Tage, an denen {LLM_SYSTEM} anders einordnet als {RULE_SYSTEM}",
            build_deviation_class_table(
                summarize_deviation_classes(agreement.deviations)
            ),
        ),
    }
    appendix: dict[str, tuple[str, pd.DataFrame]] = {
        "result_classification_events": (
            "Ereignisreihen: Bewertungstag (auslösende Skala) je Ereignis",
            build_classification_event_table(
                classification, list(e2_config["event_systems"]), stichtage
            ),
        ),
        "result_agreement": (
            f"Ereignisreihen: Übereinstimmung von {LLM_SYSTEM} mit {RULE_SYSTEM}",
            build_agreement_table(
                summarize_agreement_by_series(agreement.summary), events_labels
            ),
        ),
        "result_answer_findings": (
            "Antworten mit Verstoß im Text",
            build_violation_table(checks.findings),
        ),
        "result_phases": (
            "Urlaube: Einordnung, Zurücksetzen, Meldungen und Prognose (U = im Urlaub, R = nach der Rückkehr)",
            build_phase_overview_table(phases, labels),
        ),
    }
    for plot_reference, plot_file in (
        (reference, RETURN_PLOT_FILE),
        (context_reference, RETURN_CONTEXT_PLOT_FILE),
    ):
        build_e2_return_plot(
            summarize_return_curve(
                summaries,
                config=CONTEXT_CONFIG,
                reference_config=plot_reference,
                smoothing_days=E2Config().smoothing_days,
            ),
            output_directory,
            plot_file,
            context_label=CONFIG_LABELS[CONTEXT_CONFIG],
            reference_label=CONFIG_LABELS[plot_reference],
        )

    write_result_report(
        output_directory,
        title="E2: Einordnung durch das Sprachmodell",
        setup=build_study_setup(
            e2_config,
            standard_config,
            windows,
            labels,
            {str(event["event_id"]): str(event["title"]) for event in calendar_events},
            events_labels,
            {
                event_id: summary.mean_reduction_w
                for event_id, summary in summaries.items()
            },
            {
                row["event_id"]: row["day_error_before"]
                for row in phases.drop_duplicates("event_id").to_dict("records")
            },
            read_subtracted_appliances(list(summaries)),
            run_directory.name,
            run_config["code_version"],
        ),
        tables=tables,
        notes=NOTES
        + [f"Ausfälle des Sprachmodells in den Urlaubsläufen: {failed_days} Tage"],
        images=[f"{RETURN_PLOT_FILE}.png", f"{RETURN_CONTEXT_PLOT_FILE}.png"],
        decimals=STANDARD_CONFIG.decimals,
        appendix=appendix,
        appendix_text=[
            ("Beispielantworten des Sprachmodells", example_answer_lines(llm_outputs)),
        ],
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


def build_precheck_first_days_table(summary: GatePrecheckSummary) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "System": summary.first_days["config"],
            "Gate offen [Urlaubstag]": summary.first_days["first_gate_open_day"],
            "Drift [Urlaubstag]": summary.first_days["first_drift_day"],
            "Reset [Urlaubstag]": summary.first_days["first_reset_day"],
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


def write_precheck_report(run_directory: Path) -> None:
    run_config = read_raw_json(run_directory, "run_config")
    e2_config = run_config["e2_config"]
    target_classification = e2_config["target_classification"]

    calendar_events = load_calendar_events(E2Config().calendar_events_file)
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
