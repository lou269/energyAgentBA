from collections.abc import Collection, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    ALL_EVENTS,
    SCALE_SUSTAINED_COLUMNS,
    add_days_since_cutover,
    add_gate_flags,
    add_judgement,
    add_overall_rows,
    assign_events,
    attach_states,
    check_answer,
    count_notifications,
    find_judged_days,
    list_deviation_days,
    list_events,
    local_dates,
    summarize_forecast_errors,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
    RULE_SYSTEM,
    SUSTAINED_CLASSIFICATION,
)


def summarize_reduction_by_day(
    mains_series: pd.Series,
    absence_adjusted_series: pd.Series,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.DataFrame:
    """Wie stark senkt das Herausrechnen der Kanäle Mains je Tag der Abwesenheit, unabhängig von den Anomalie-Schwellen"""
    raw_window = mains_series.loc[
        (mains_series.index >= window_start) & (mains_series.index < window_end)
    ]
    adjusted_window = absence_adjusted_series.loc[raw_window.index]

    local_day = local_dates(raw_window.index)

    comparison = pd.DataFrame(
        {
            "mains_before_w": raw_window.groupby(local_day).mean(),
            "mains_after_w": adjusted_window.groupby(local_day).mean(),
        }
    )
    comparison.index.name = "date"
    comparison["reduction_w"] = (
        comparison["mains_before_w"] - comparison["mains_after_w"]
    )

    return comparison.reset_index()


# Spalten aus anomaly.csv, an denen sich ablesen lässt, wie weit der Urlaub von den Schwellen entfernt ist,
# dazu die anhaltenden Skalen, über die das Gate auch öffnet
PRECHECK_ANOMALY_COLUMNS = [
    "today_mean",
    "weekday_expected",
    "daily_score",
    "weekday_score",
    "weekly_score",
    "long_term_deviation_pct",
    "weekly_anomaly_streak_days",
    "long_term_anomaly_streak_days",
    "anomaly_level",
    "sustained_drift",
    "value_implausible",
] + SCALE_SUSTAINED_COLUMNS

PHASES = ("before", "absence", "after_return")

# Spalten der Ereignis-Szenarien, die summarize_classification braucht
CLASSIFICATION_RESULT_COLUMNS = [
    "config",
    "kind",
    "cutover_date",
    "decision_time",
    "analyzed_day",
    "classification",
    "adaption_action",
    "error",
    "dominant_scale",
    "sustained_drift",
    "gate_open",
] + SCALE_SUSTAINED_COLUMNS


def summarize_classification(
    results: pd.DataFrame, event_series: Mapping[str, tuple[tuple[int, str], ...]]
) -> pd.DataFrame:
    """Eine Zeile je Reihe, System und Ereignis: erwartete Klasse, Bewertungstag, Klasse an diesem Tag, auslösende Skala, erkannt und richtig eingeordnet. Ab der ersten Handlung (Ausschluss des Festhängers) sehen die Systeme verschiedene Zustände"""
    days = add_days_since_cutover(results).rename(columns={"kind": "series"})
    keys = ["series", "cutover_date", "config", "event"]
    tables = []

    for series, events in event_series.items():
        # die Kontrolle hat keine Ereignisse und zählt nicht in die Quote
        if not events:
            continue
        event_list = list_events(events)
        series_days = days.loc[days["series"].eq(series)]
        event_days = series_days.assign(
            event=assign_events(series_days, event_list)
        ).dropna(subset=["event"])
        event_days = event_days.merge(event_list, on="event")
        tables.append(
            add_judgement(
                series_days[["series", "cutover_date", "config"]]
                .drop_duplicates()
                .merge(event_list, how="cross"),
                find_judged_days(event_days, keys),
                keys,
            ).sort_values(["event", "config"])
        )

    return pd.concat(tables, ignore_index=True)


def summarize_classification_rates(events: pd.DataFrame) -> pd.DataFrame:
    """Je System und erwarteter Klasse sowie über alle Ereignisse: Ereignisse, erkannt (es gibt einen Bewertungstag), richtig eingeordnet und der Anteil richtiger unter den erkannten"""
    rates = (
        add_overall_rows(events, "expected", ALL_EVENTS)
        .groupby(["config", "expected"], as_index=False)
        .agg(
            events=("event", "size"),
            detected=("detected", "sum"),
            correct=("correct", "sum"),
        )
    )

    return rates.assign(correct_pct=rates["correct"] / rates["detected"] * 100)


@dataclass(frozen=True)
class RuleAgreement:
    summary: pd.DataFrame
    deviations: pd.DataFrame


def summarize_rule_agreement(
    results: pd.DataFrame, *, rule_system: str, llm_system: str
) -> RuleAgreement:
    """Je Reihe (auch die Kontrolle ohne Ereignis): verglichene Tage, Tage mit offenem Gate, Tage mit anderer Klasse als die Regel und Meldungen beider Systeme, dazu die abweichenden Tage"""
    days = add_days_since_cutover(results).rename(columns={"kind": "series"})
    keys = ["cutover_date", "series"]
    deviations = list_deviation_days(
        days, keys, ["analyzed_day"], rule_system=rule_system, llm_system=llm_system
    )
    notifications = count_notifications(
        days.loc[days["config"].isin([rule_system, llm_system])],
        keys + ["config"],
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    ).pivot(index=keys, columns="config", values="notification_days")

    llm_days = days.loc[days["config"].eq(llm_system)]
    summary = llm_days.groupby(keys).agg(
        days=("gate_open", "size"), gate_open_days=("gate_open", "sum")
    )

    return RuleAgreement(
        summary=summary.assign(
            deviation_days=deviations.groupby(keys)
            .size()
            .reindex(summary.index, fill_value=0),
            rule_notification_days=notifications[rule_system],
            llm_notification_days=notifications[llm_system],
        ).reset_index(),
        deviations=deviations,
    )


@dataclass(frozen=True)
class FalseAlarms:
    resets: pd.DataFrame
    notifications: pd.DataFrame


def summarize_false_alarms(
    results: pd.DataFrame,
    event_series: Mapping[str, tuple[tuple[int, str], ...]],
    *,
    rule_system: str,
    llm_system: str,
) -> FalseAlarms:
    """Über alle Cutover der Ereignisreihen, je Reihe und alle zusammen.
    resets: in den Reihen, in denen kein Ereignis einen Reset verlangt (Kontrolle, Spitzen, Festhänger), die Tage, die Resets der Regel, die des LLM-Systems und davon falsch: der Reset des LLM-Systems an einem Tag, an dem die Regel nicht zurücksetzt.
    notifications: je System die Tage außerhalb der Ereignisse und die Meldungen darauf. Ein Einzeltag-Ereignis zählt nur an seinem ersten Einordnungstag, ein anhaltendes von dort an
    """
    days = add_days_since_cutover(results).rename(columns={"kind": "series"})
    order = list(event_series) + [ALL_EVENTS]
    tables = []
    resetless = []

    for series, events in event_series.items():
        event_list = list_events(events)
        if event_list["expected"].ne(SUSTAINED_CLASSIFICATION).all():
            resetless.append(series)
        series_days = days.loc[days["series"].eq(series)]
        joined = series_days.assign(event=assign_events(series_days, event_list)).merge(
            event_list, on="event", how="left"
        )
        in_event = joined["event"].notna() & (
            joined["expected"].eq(SUSTAINED_CLASSIFICATION)
            | joined["days_since_cutover"].eq(joined["first_day"])
        )
        tables.append(
            joined.assign(
                outside=~in_event,
                notification=joined["classification"].isin(
                    NOTIFICATION_CLASSIFICATIONS
                ),
                reset=joined["adaption_action"].eq("advance_history_start"),
            )
        )
    flagged = pd.concat(tables, ignore_index=True)

    return FalseAlarms(
        resets=_count_false_resets(
            flagged.loc[flagged["series"].isin(resetless)],
            order,
            rule_system=rule_system,
            llm_system=llm_system,
        ),
        notifications=_count_notifications_outside(
            flagged.loc[flagged["outside"]], order
        ),
    )


def _sort_by_series(
    counts: pd.DataFrame, keys: list[str], order: list[str]
) -> pd.DataFrame:
    counts["series"] = pd.Categorical(counts["series"], order, ordered=True)

    return counts.sort_values(keys).astype({"series": str}).reset_index(drop=True)


def _count_false_resets(
    days: pd.DataFrame, order: list[str], *, rule_system: str, llm_system: str
) -> pd.DataFrame:
    keys = ["series", "cutover_date", "days_since_cutover"]
    paired = days.loc[days["config"].eq(rule_system), keys + ["reset"]].merge(
        days.loc[days["config"].eq(llm_system), keys + ["reset"]],
        on=keys,
        suffixes=("_rule", "_llm"),
    )
    paired["false_reset"] = paired["reset_llm"] & paired["reset_rule"].eq(False)
    counts = (
        add_overall_rows(paired, "series", ALL_EVENTS)
        .groupby("series", as_index=False)
        .agg(
            days=("series", "size"),
            rule_reset_days=("reset_rule", "sum"),
            llm_reset_days=("reset_llm", "sum"),
            false_reset_days=("false_reset", "sum"),
        )
    )

    return _sort_by_series(counts, ["series"], order)


def _count_notifications_outside(days: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    counts = (
        add_overall_rows(days, "series", ALL_EVENTS)
        .groupby(["config", "series"], as_index=False)
        .agg(days=("series", "size"), notification_days=("notification", "sum"))
    )

    return _sort_by_series(counts, ["config", "series"], order)


@dataclass(frozen=True)
class AnswerChecks:
    summary: pd.DataFrame
    findings: pd.DataFrame


def summarize_answer_checks(
    outputs: pd.DataFrame,
    states: pd.DataFrame,
    *,
    target_classification: str,
    control_words: tuple[str, ...],
    number_tolerance: float,
    rounding_step: float,
    prompt_numbers: tuple[float, ...],
) -> AnswerChecks:
    """Je Lauf und System: Antworten, davon mit fehlendem Beleg zur Klasse, davon mit Verstoß im Text, dazu die Antworten der Zielklasse und wie viele davon belegt sind (bei absence: ein Kalendereintrag, der existiert). Die Funde nennen Tag und Grund"""
    checked = attach_states(outputs, states)
    checks = [
        check_answer(
            row,
            row["state"],
            control_words=control_words,
            number_tolerance=number_tolerance,
            rounding_step=rounding_step,
            prompt_numbers=prompt_numbers,
        )
        for _, row in checked.iterrows()
    ]
    checked = checked.assign(
        violations=[violations for violations, _ in checks],
        missing_evidence=[missing for _, missing in checks],
    )
    target = checked["classification"].eq(target_classification)
    unsupported = checked["missing_evidence"].ne("")
    flagged = checked.assign(
        violation=checked["violations"].ne(""),
        unsupported=unsupported,
        target_answer=target,
        target_supported=target & unsupported.eq(False),
    )
    summary = flagged.groupby(["scenario", "config"], as_index=False).agg(
        answers=("config", "size"),
        unsupported_answers=("unsupported", "sum"),
        violation_answers=("violation", "sum"),
        target_answers=("target_answer", "sum"),
        target_supported_answers=("target_supported", "sum"),
    )
    findings = (
        flagged.loc[
            flagged["violation"] | flagged["unsupported"],
            [
                "scenario",
                "config",
                "analyzed_day",
                "classification",
                "violations",
                "missing_evidence",
            ],
        ]
        .sort_values(["scenario", "config", "analyzed_day"])
        .reset_index(drop=True)
    )

    return AnswerChecks(summary=summary, findings=findings)


def by_phase(column: pd.Series) -> pd.Series:
    # Schlüssel für sort_values: Phasen in zeitlicher statt alphabetischer Reihenfolge
    return column.map(PHASES.index) if column.name == "phase" else column


def absence_phase(
    dates: pd.Series, window_start: pd.Timestamp, window_end: pd.Timestamp
) -> np.ndarray:
    """Phase je lokalem Kalendertag (Text), für eingeordnete Tage wie für Prognosetage"""
    start_day, end_day = local_dates([window_start, window_end])
    days = pd.to_datetime(dates)

    return np.select([days < start_day, days < end_day], PHASES[:2], PHASES[2])


def label_absence_days(
    comparison: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    target_classification: str,
    absence_event_id: str,
    counter_configs: Collection[str],
) -> pd.DataFrame:
    start_day = local_dates([window_start])[0]
    days = add_gate_flags(
        comparison.merge(
            anomaly[["config", "analyzed_day"] + PRECHECK_ANOMALY_COLUMNS],
            on=["config", "analyzed_day"],
            how="left",
        )
    )
    analyzed = pd.to_datetime(days["analyzed_day"])
    target = days["classification"].eq(target_classification)
    # im Gegenfall meint Eintrag keine Abwesenheit
    supported = (
        target
        & days["adaption_reason"].fillna("").str.contains(absence_event_id, regex=False)
        & ~days["config"].isin(counter_configs)
    )

    drift_gate = days["sustained_drift"].eq(True)

    return days.assign(
        phase=absence_phase(days["analyzed_day"], window_start, window_end),
        absence_day=(analyzed - start_day).dt.days,
        drift_gate=drift_gate,
        # das Gate öffnet auch über eine einzelne anhaltende Skala, ohne auffälligen Tag und ohne Drift
        single_scale_gate=days["gate_open"]
        & ~days["alarm"]
        & ~drift_gate
        & ~days["value_implausible"].eq(True),
        reset=days["adaption_action"].eq("advance_history_start"),
        absence_hit=supported,
        unsupported_absence=target & ~supported,
    )


def summarize_phases(days: pd.DataFrame) -> pd.DataFrame:
    flagged = days.assign(
        new_pattern=days["classification"].eq("new_pattern"),
        low=days["classification"].eq("low"),
        peak=days["classification"].eq("peak"),
        absence_classified=days["classification"].eq("absence"),
        failed=days["error"].notna(),
    )
    phases = flagged.groupby(["config", "phase"], as_index=False).agg(
        days=("phase", "size"),
        gate_open_days=("gate_open", "sum"),
        alarm_days=("alarm", "sum"),
        drift_gate_days=("drift_gate", "sum"),
        single_scale_gate_days=("single_scale_gate", "sum"),
        new_pattern_days=("new_pattern", "sum"),
        low_days=("low", "sum"),
        peak_days=("peak", "sum"),
        absence_classified_days=("absence_classified", "sum"),
        reset_days=("reset", "sum"),
        failed_days=("failed", "sum"),
    )
    notifications = count_notifications(
        flagged,
        ["config", "phase"],
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    )

    return (
        phases.merge(
            notifications[["config", "phase", "notification_days"]],
            on=["config", "phase"],
        )
        .sort_values(["config", "phase"], key=by_phase)
        .reset_index(drop=True)
    )


@dataclass(frozen=True)
class E2Summary:
    phases: pd.DataFrame
    absence_classification: pd.DataFrame
    calendar_use: pd.DataFrame
    calendar_calls: pd.DataFrame
    forecast: pd.DataFrame
    context_forecast: pd.DataFrame
    deviations: pd.DataFrame
    timeline: pd.DataFrame
    reduction: pd.DataFrame
    mean_reduction_w: float
    first_analyzed_day: str
    last_analyzed_day: str


def summarize_phase_forecast(
    forecast_days: pd.DataFrame, reference_config: str
) -> pd.DataFrame:
    # Fehler je Phase und System, gepaart gegen reference_config, dazu der Bias mit Vorzeichen
    bias = forecast_days.groupby(["config", "phase"], as_index=False).agg(
        mean_day_bias_w=("day_bias_w", "mean")
    )

    return (
        summarize_forecast_errors(forecast_days, ["phase"], reference_config)
        .merge(bias, on=["config", "phase"])
        .sort_values(["config", "phase"], key=by_phase)
        .reset_index(drop=True)
    )


def summarize_e2(
    comparison: pd.DataFrame,
    anomaly: pd.DataFrame,
    calendar_availability: pd.DataFrame,
    reduction: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    target_classification: str,
    absence_event_id: str,
    counter_configs: Collection[str],
    reference_config: str,
    context_reference_config: str,
) -> E2Summary:
    days = label_absence_days(
        comparison,
        anomaly,
        window_start=window_start,
        window_end=window_end,
        target_classification=target_classification,
        absence_event_id=absence_event_id,
        counter_configs=counter_configs,
    )
    during = days.loc[days["phase"].eq("absence")]

    absence_classification = during.groupby("config").agg(
        absence_days=("phase", "size"),
        gate_open_days=("gate_open", "sum"),
        hit_days=("absence_hit", "sum"),
    )
    absence_classification["hit_rate"] = (
        absence_classification["hit_days"] / absence_classification["gate_open_days"]
    )
    absence_classification["first_hit_day"] = (
        during.loc[during["absence_hit"]]
        .groupby("config")["absence_day"]
        .min()
        .astype("Int64")
    )
    absence_classification["unsupported_absence_days"] = days.groupby("config")[
        "unsupported_absence"
    ].sum()

    classified = calendar_availability.merge(
        days[["config", "analyzed_day", "phase"]], on=["config", "analyzed_day"]
    )
    calendar_use = classified.groupby(["config", "phase"], as_index=False).agg(
        classified_days=("calendar_available", "size"),
        calendar_days=("calendar_available", "sum"),
    )
    # mit Kalender-Tool steht der Kalender nur nach einem Abruf im State, nützlich ist er, wenn ein Eintrag den Tag abdeckt
    called = classified["calendar_available"].eq(True)
    covered = classified["phase"].eq("absence")
    calendar_calls = (
        classified.assign(
            useful=called & covered,
            superfluous=called & ~covered,
            missed=~called & covered,
            saved=~called & ~covered,
        )
        .groupby("config", as_index=False)[["useful", "superfluous", "missed", "saved"]]
        .sum()
    )

    # Fehler und Phase gehören zum Prognosetag, die Prognose entsteht nach der Einordnung des Vortags
    forecast_day = local_dates(days["decision_time"]).strftime("%Y-%m-%d")
    forecast_days = days.assign(
        forecast_day=forecast_day,
        phase=absence_phase(forecast_day, window_start, window_end),  # type: ignore
    )

    # Tage mit anderer Klasse als die Regel, gepaart über den Urlaubstag, alle Systeme mit LLM gegen SYS2
    llm_configs = [
        config
        for config in days["config"].unique()
        if config not in (reference_config, RULE_SYSTEM)
    ]
    paired_days = days.rename(columns={"absence_day": "days_since_cutover"})
    deviations = pd.concat(
        [
            list_deviation_days(
                paired_days,
                [],
                ["analyzed_day"],
                rule_system=RULE_SYSTEM,
                llm_system=config,
            ).assign(config=config)
            for config in llm_configs
        ],
        ignore_index=True,
    )

    # je Kalendertag Ist und Prognose für diesen Tag, dazu die Einordnung dieses Tages, die am Folgetag getroffen wird
    actual_w = days.groupby("analyzed_day")["today_mean"].first()
    forecast_w = forecast_days.set_index(["config", "forecast_day"])["day_forecast_w"]
    timeline = (
        days[
            [
                "config",
                "analyzed_day",
                "absence_day",
                "phase",
                "classification",
                "adaption_action",
            ]
        ]
        .assign(actual_w=days["analyzed_day"].map(actual_w))
        .merge(
            forecast_w.rename("forecast_w"),
            left_on=["config", "analyzed_day"],
            right_index=True,
            how="left",
        )
    )

    return E2Summary(
        phases=summarize_phases(days),
        absence_classification=absence_classification.reset_index(),
        calendar_use=calendar_use.sort_values(["config", "phase"], key=by_phase),
        calendar_calls=calendar_calls,
        forecast=summarize_phase_forecast(forecast_days, reference_config),
        context_forecast=summarize_phase_forecast(
            forecast_days, context_reference_config
        ),
        deviations=deviations,
        timeline=timeline.sort_values(["config", "absence_day"]).reset_index(drop=True),
        reduction=reduction,
        mean_reduction_w=reduction["reduction_w"].mean(),
        first_analyzed_day=comparison["analyzed_day"].min(),
        last_analyzed_day=comparison["analyzed_day"].max(),
    )


@dataclass(frozen=True)
class GatePrecheckSummary:
    phases: pd.DataFrame
    first_days: pd.DataFrame
    days_from_absence: pd.DataFrame


def summarize_gate_precheck(
    comparison: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    target_classification: str,
    absence_event_id: str,
    counter_configs: Collection[str],
) -> GatePrecheckSummary:
    days = label_absence_days(
        comparison,
        anomaly,
        window_start=window_start,
        window_end=window_end,
        target_classification=target_classification,
        absence_event_id=absence_event_id,
        counter_configs=counter_configs,
    )
    from_absence = days.loc[days["phase"] != "before"]
    first_days = pd.DataFrame(
        {
            "first_gate_open_day": from_absence.loc[from_absence["gate_open"]]
            .groupby("config")["absence_day"]
            .min(),
            "first_drift_day": from_absence.loc[from_absence["drift_gate"]]
            .groupby("config")["absence_day"]
            .min(),
            "first_reset_day": from_absence.loc[from_absence["reset"]]
            .groupby("config")["absence_day"]
            .min(),
        },
        index=pd.Index(sorted(days["config"].unique()), name="config"),
    )

    return GatePrecheckSummary(
        phases=summarize_phases(days),
        first_days=first_days.astype("Int64").reset_index(),
        days_from_absence=from_absence[
            ["config", "absence_day", "analyzed_day", "phase"]
            + PRECHECK_ANOMALY_COLUMNS
            + ["classification", "adaption_action"]
        ]
        .sort_values(["config", "absence_day"])
        .reset_index(drop=True),
    )


ABSENCE_PHASE = "absence"
AFTER_RETURN_PHASE = "after_return"
SINGLE_SCALES = ("weekly", "long_term")


def summarize_absence_overview(
    summaries: Mapping[str, E2Summary], configs: Collection[str]
) -> pd.DataFrame:
    tables = []
    for event_id, summary in summaries.items():
        in_absence = summary.phases.loc[
            summary.phases["phase"].eq(ABSENCE_PHASE),
            ["config", "reset_days", "low_days", "absence_classified_days"],
        ]
        tables.append(
            summary.absence_classification.merge(
                in_absence, on="config", how="left"
            ).assign(event_id=event_id)
        )
    overview = pd.concat(tables, ignore_index=True)

    return overview.loc[overview["config"].isin(configs)].reset_index(drop=True)


def total_absence_by_variant(overview: pd.DataFrame) -> pd.DataFrame:
    return (
        overview.assign(absence_event=overview["absence_classified_days"].gt(0))
        .groupby("config", as_index=False)
        .agg(
            absence_events=("absence_event", "sum"),
            gate_open_days=("gate_open_days", "sum"),
            absence_days=("absence_classified_days", "sum"),
            unsupported_absence_days=("unsupported_absence_days", "sum"),
            reset_days=("reset_days", "sum"),
        )
        .assign(events=overview["event_id"].nunique())
    )


def summarize_agreement_by_series(summary: pd.DataFrame) -> pd.DataFrame:
    counts = [
        "days",
        "gate_open_days",
        "deviation_days",
        "rule_notification_days",
        "llm_notification_days",
    ]
    by_series = summary.groupby("series", as_index=False, sort=False)[counts].sum()
    total = by_series[counts].sum().to_frame().T.assign(series=ALL_EVENTS)

    return pd.concat([by_series, total[by_series.columns]], ignore_index=True)


def summarize_answer_overview(
    answer_summary: pd.DataFrame, findings: pd.DataFrame
) -> pd.DataFrame:
    unsupported = findings.loc[findings["missing_evidence"].ne("")]
    violations = findings["violations"]

    return pd.DataFrame(
        [
            {
                "answers": int(answer_summary["answers"].sum()),
                "unsupported_answers": len(unsupported),
                "unsupported_classes": ", ".join(
                    sorted(unsupported["classification"].unique())
                ),
                "missing_paths": ", ".join(
                    sorted(set(unsupported["missing_evidence"]))
                ),
                "violation_answers": int(violations.ne("").sum()),
                "number_answers": int(violations.str.contains("number:").sum()),
                "control_answers": int(violations.str.contains("control:").sum()),
                "target_answers": int(answer_summary["target_answers"].sum()),
                "target_supported_answers": int(
                    answer_summary["target_supported_answers"].sum()
                ),
            }
        ]
    )


def summarize_return_forecast(
    summaries: Mapping[str, E2Summary], context_config: str
) -> pd.DataFrame:
    columns = ["mean_delta", "delta_standard_error", "exceeds_noise"]
    rows = []
    for event_id, summary in summaries.items():
        row = {"event_id": event_id}
        for prefix, table in (
            ("reference", summary.forecast),
            ("context", summary.context_forecast),
        ):
            found = table.loc[
                table["config"].eq(context_config)
                & table["phase"].eq(AFTER_RETURN_PHASE),
                columns,
            ].iloc[0]
            row |= {f"{prefix}_{column}": found[column] for column in columns}
        rows.append(row)

    return pd.DataFrame(rows)


def summarize_calendar_call_totals(
    summaries: Mapping[str, E2Summary], tool_configs: Collection[str]
) -> pd.DataFrame:
    calls = pd.concat(
        [
            summary.calendar_calls.loc[
                summary.calendar_calls["config"].isin(tool_configs)
            ].assign(event_id=event_id)
            for event_id, summary in summaries.items()
        ],
        ignore_index=True,
    )
    counts = ["useful", "superfluous", "missed", "saved"]
    total = calls[counts].sum().to_frame().T.assign(event_id=ALL_EVENTS)

    return pd.concat(
        [calls[["event_id"] + counts], total[["event_id"] + counts]], ignore_index=True
    )


def summarize_classification_comparison(
    events: pd.DataFrame, *, rule_system: str, llm_system: str
) -> pd.DataFrame:
    rates = summarize_classification_rates(events)
    by_system = {
        config: rates.loc[rates["config"].eq(config)].set_index("expected")
        for config in (llm_system, rule_system)
    }
    llm_events = events.loc[events["config"].eq(llm_system)]
    single_scale = llm_events.loc[
        llm_events["classification"].eq(SUSTAINED_CLASSIFICATION)
        & llm_events["trigger_scale"].isin(SINGLE_SCALES)
    ]
    llm_rates = by_system[llm_system]

    return pd.DataFrame(
        {
            "expected": llm_rates.index,
            "events": llm_rates["events"].to_numpy(),
            "llm_detected": llm_rates["detected"].to_numpy(),
            "llm_correct": llm_rates["correct"].to_numpy(),
            "rule_detected": by_system[rule_system]
            .loc[llm_rates.index, "detected"]
            .to_numpy(),
            "rule_correct": by_system[rule_system]
            .loc[llm_rates.index, "correct"]
            .to_numpy(),
            "llm_single_scale": [
                len(single_scale) if expected == SUSTAINED_CLASSIFICATION else pd.NA
                for expected in llm_rates.index
            ],
        }
    )


def summarize_deviation_classes(deviations: pd.DataFrame) -> pd.DataFrame:
    pairs = deviations.fillna({"classification_llm": "Ausfall"})

    return (
        pairs.groupby(["classification_rule", "classification_llm"], as_index=False)
        .size()
        .rename(columns={"size": "days"})
        .sort_values("days", ascending=False, kind="stable")
        .reset_index(drop=True)
    )


def _single_value(table: pd.DataFrame, key_column: str, key: str, column: str):
    return table.loc[table[key_column].eq(key), column].to_numpy()[0]


def summarize_tf2_criteria(
    comparison: pd.DataFrame,
    absence: pd.DataFrame,
    answer_summary: pd.DataFrame,
    *,
    context_config: str,
) -> pd.DataFrame:
    correct = int(_single_value(comparison, "expected", ALL_EVENTS, "llm_correct"))
    detected = int(_single_value(comparison, "expected", ALL_EVENTS, "llm_detected"))
    correct_pct = 100 * correct / detected
    hits = absence.loc[absence["config"].eq(context_config), "hit_days"]
    unsupported_absence = int(absence["unsupported_absence_days"].sum())
    unsupported_answers = int(answer_summary["unsupported_answers"].sum())
    answers = int(answer_summary["answers"].sum())

    return pd.DataFrame(
        [
            {
                "criterion": "correct",
                "value": correct,
                "total": detected,
                "share_pct": correct_pct,
                "fulfilled": correct_pct >= 80,
            },
            {
                "criterion": "hits",
                "value": ", ".join(str(int(days)) for days in hits),
                "fulfilled": bool(hits.gt(0).all()),
            },
            {
                "criterion": "absence_without_entry",
                "value": unsupported_absence,
                "fulfilled": unsupported_absence == 0,
            },
            {
                "criterion": "missing_evidence",
                "value": unsupported_answers,
                "total": answers,
                "share_pct": 100 * unsupported_answers / answers,
                "fulfilled": unsupported_answers == 0,
            },
        ]
    )


def summarize_phase_overview(
    summaries: Mapping[str, E2Summary], configs: Collection[str]
) -> pd.DataFrame:
    rows = []
    for event_id, summary in summaries.items():
        phases = summary.phases.set_index(["config", "phase"])
        forecast = summary.forecast.set_index(["config", "phase"])
        for config in configs:
            if (config, ABSENCE_PHASE) not in phases.index:
                continue
            during = phases.loc[(config, ABSENCE_PHASE), :]
            after = phases.loc[(config, AFTER_RETURN_PHASE), :]
            rows.append(
                {
                    "config": config,
                    "event_id": event_id,
                    "gate_open_days": during["gate_open_days"],
                    "low_days": during["low_days"],
                    "absence_days": during["absence_classified_days"],
                    "reset_days": during["reset_days"],
                    "reset_days_after": after["reset_days"],
                    "notification_days": during["notification_days"],
                    "notification_days_after": after["notification_days"],
                    "day_error_before": forecast.at[
                        (config, "before"), "mean_day_error_w"
                    ],
                    "day_error_absence": forecast.at[
                        (config, ABSENCE_PHASE), "mean_day_error_w"
                    ],
                    "day_error_after_return": forecast.at[
                        (config, AFTER_RETURN_PHASE), "mean_day_error_w"
                    ],
                    "bias_absence": forecast.at[
                        (config, ABSENCE_PHASE), "mean_day_bias_w"
                    ],
                    "bias_after_return": forecast.at[
                        (config, AFTER_RETURN_PHASE), "mean_day_bias_w"
                    ],
                }
            )

    return pd.DataFrame(rows)


def count_failed_days(summaries: Mapping[str, E2Summary]) -> int:
    return int(
        sum(summary.phases["failed_days"].sum() for summary in summaries.values())
    )


def summarize_return_curve(
    summaries: Mapping[str, E2Summary],
    *,
    config: str,
    reference_config: str,
    smoothing_days: int,
) -> pd.DataFrame:
    deltas = []
    for event_id, summary in summaries.items():
        after = summary.timeline.loc[
            summary.timeline["phase"].eq(AFTER_RETURN_PHASE)
            & summary.timeline["config"].isin([config, reference_config])
        ]
        errors = after.assign(day_error=(after["forecast_w"] - after["actual_w"]).abs())
        wide = errors.pivot(
            index="absence_day", columns="config", values="day_error"
        ).dropna()
        delta = wide[config] - wide[reference_config]
        deltas.append(
            (delta.set_axis(delta.index - delta.index.min())).rename(event_id)
        )

    curve = pd.concat(deltas, axis=1).mean(axis=1).sort_index()

    return (
        curve.rolling(smoothing_days, min_periods=1)
        .mean()
        .rename("delta")
        .rename_axis("day_since_return")
        .reset_index()
    )
