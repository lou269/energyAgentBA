from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
    add_days_since_cutover,
    add_weeks,
    add_judgement,
    assign_events,
    count_notifications,
    find_judged_days,
    list_event_series,
    merge_cycle_days,
    summarize_forecast_errors,
    summarize_latency,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
    SUSTAINED_CLASSIFICATION,
)
from experiments.e3_system_compare.e3_config import SCENARIO_DIRECTORY


# über mehrere Fälle zusammengefasste Tage werden je Cutover, Reihe und Zeitpunkt gepaart
POOL_PAIR_KEYS = ("cutover_date", "series", "decision_time")
SERIES_KEYS = ["cutover_date", "series"]
EVENT_KEYS = ["cutover_date", "config", "event"]
FORECAST_COLUMNS = [
    "config",
    "mean_day_error_w",
    "mean_mae_w",
    "mean_mape_pct",
    "paired_count",
    "mean_delta",
    "delta_standard_error",
    "better_share",
    "exceeds_noise",
    "mae_delta_w",
]

RESULT_COLUMNS = (
    [
        "scenario",
        "series",
        "cutover_date",
        "config",
        "decision_time",
        "analyzed_day",
        "days_since_cutover",
        "classification",
        "classifier_called",
        "adaption_action",
        "error",
        "day_error_w",
        "mae_w",
        "mape_pct",
        "anomaly_level",
        "dominant_scale",
        "alarm",
        "gate_open",
        "sustained_drift",
    ]
    + SCALE_VALUE_COLUMNS
    + SCALE_SUSTAINED_COLUMNS
)


def read_e3_results(
    summary: pd.DataFrame, anomaly: pd.DataFrame, *, series: str, cutover_date: str
) -> pd.DataFrame:
    days = merge_cycle_days(summary, anomaly).assign(
        series=series,
        cutover_date=cutover_date,
        scenario=SCENARIO_DIRECTORY.format(series=series, cutover_date=cutover_date),
    )
    # das LLM wurde gefragt, auch wenn es keine gültige Antwort lieferte
    days["classifier_called"] = days["explanation"].notna() | days["error"].notna()

    return add_days_since_cutover(days)[RESULT_COLUMNS]


def _assign_series_events(results: pd.DataFrame, event_list: pd.DataFrame) -> pd.Series:
    numbers = pd.Series(pd.NA, index=results.index, dtype="Int64")
    for series, table in event_list.groupby("series"):
        rows = results["series"].eq(series)
        numbers.loc[rows] = assign_events(results.loc[rows], table) + (
            table["event"].min() - 1
        )

    return numbers


def _find_separation_days(results: pd.DataFrame) -> pd.DataFrame:
    # ab dem ersten Tag mit verschiedener Aktion haben die Systeme verschiedene Zustände, davor muss die Prognose bei allen gleich sein
    rows = []
    for (cutover_date, series), group in results.groupby(SERIES_KEYS):
        by_day = group.groupby("days_since_cutover")
        actions_differ = by_day["adaption_action"].nunique().gt(1)
        spread = by_day["mae_w"].max() - by_day["mae_w"].min()

        separation_day = actions_differ.idxmax() if actions_differ.any() else pd.NA
        before = (
            spread if pd.isna(separation_day) else spread[spread.index < separation_day]  # type: ignore
        )
        rows.append(
            {
                "cutover_date": cutover_date,
                "series": series,
                "separation_day": separation_day,
                "forecast_identical_before": bool(
                    np.isclose(before.fillna(0), 0).all()
                ),
            }
        )

    return pd.DataFrame(rows).astype({"separation_day": "Int64"})


def _count_lead_notifications(
    event_days: pd.DataFrame, judged_days: pd.DataFrame
) -> pd.DataFrame:
    # peak-Meldungen vor dem Bewertungstag einer dauerhaften Änderung zählen als Meldung, nicht als Fehler
    before_judged = event_days.merge(
        judged_days[EVENT_KEYS + ["judged_day"]], on=EVENT_KEYS, how="left"
    )
    before_judged = before_judged.loc[
        before_judged["expected"].eq(SUSTAINED_CLASSIFICATION)
        & ~before_judged["days_since_cutover"].ge(before_judged["judged_day"])
    ]

    return (
        before_judged.assign(
            notification=before_judged["classification"].isin(
                NOTIFICATION_CLASSIFICATIONS
            )
        )
        .groupby(EVENT_KEYS, as_index=False)
        .agg(lead_notification_days=("notification", "sum"))
    )


def _summarize_events(
    event_days: pd.DataFrame, event_list: pd.DataFrame, separations: pd.DataFrame
) -> pd.DataFrame:
    """Je Cutover, System und Ereignis die Einordnung am Bewertungstag, ohne Bewertungstag nicht erkannt, dazu Skala, Vorlauf-Meldungen und Reset"""
    judged_days = find_judged_days(event_days, EVENT_KEYS)
    table = add_judgement(
        event_days[["cutover_date", "config"]]
        .drop_duplicates()
        .merge(event_list, how="cross"),
        judged_days,
        EVENT_KEYS,
    )

    resets = (
        event_days.loc[event_days["adaption_action"].eq("advance_history_start")]
        .groupby(EVENT_KEYS, as_index=False)
        .agg(reset_day=("days_since_cutover", "min"))
    )
    table = (
        table.merge(
            _count_lead_notifications(event_days, table), on=EVENT_KEYS, how="left"
        )
        .merge(resets, on=EVENT_KEYS, how="left")
        .merge(
            separations[["cutover_date", "series", "separation_day"]],
            on=["cutover_date", "series"],
            how="left",
        )
    )
    # vor Beginn des Ereignisses hat schon ein System anders gehandelt, die Einordnung beruht nicht mehr auf demselben Zustand
    table["after_separation"] = (
        table["separation_day"].le(table["start_day"]).fillna(False)
    )
    day_columns = ["judged_day", "lead_notification_days", "reset_day"]
    table[day_columns] = table[day_columns].astype("Int64")

    return table.sort_values(["cutover_date", "event", "config"]).reset_index(drop=True)


def _list_cases(events_table: pd.DataFrame, llm_system: str) -> pd.DataFrame:
    """Je Cutover und Reihe mit Dauerlast ein Fall: ausgelöst = das LLM-System hat in der Reihe zurückgesetzt, reset_day ist der erste Reset"""
    cases = (
        events_table.loc[
            events_table["config"].eq(llm_system)
            & events_table["expected"].eq(SUSTAINED_CLASSIFICATION)
        ]
        .groupby(SERIES_KEYS, as_index=False)
        .agg(reset_day=("reset_day", "min"))
    )
    cases["triggered"] = cases["reset_day"].notna()

    return cases


def _summarize_control(results: pd.DataFrame) -> pd.DataFrame:
    control = results.loc[results["series"].eq("control")]
    keys = ["cutover_date", "config"]
    resets = (
        control.assign(reset=control["adaption_action"].eq("advance_history_start"))
        .groupby(keys, as_index=False)
        .agg(resets=("reset", "sum"))
    )

    return count_notifications(
        control,
        keys,
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    ).merge(resets, on=keys)


def _window_after_reset(
    results: pd.DataFrame,
    cases: pd.DataFrame,
    systems: list[str],
    *,
    include_reset_day: bool,
) -> pd.DataFrame:
    """Tage der ausgelösten Fälle ab dem Reset (die Prognose desselben Tages enthält ihn schon, die Einordnung dieses Tages nicht), mit day_since_reset"""
    triggered = cases.loc[cases["triggered"], SERIES_KEYS + ["reset_day"]].astype(
        {"reset_day": int}
    )
    window = results.loc[results["config"].isin(systems)].merge(
        triggered, on=SERIES_KEYS
    )
    since = window["days_since_cutover"] - window["reset_day"]
    window = window.assign(day_since_reset=since)

    return window.loc[since.ge(0) if include_reset_day else since.gt(0)]


def _forecast_errors(
    days: pd.DataFrame,
    keys: list[str],
    reference_system: str,
    pair_keys: tuple[str, ...] = ("decision_time",),
) -> pd.DataFrame:
    # ohne ausgelösten Fall gibt es nichts zu vergleichen
    if days.empty:
        return pd.DataFrame(columns=keys + FORECAST_COLUMNS)

    return summarize_forecast_errors(days, keys, reference_system, pair_keys)


def _compare_forecasts(
    window: pd.DataFrame, cases: pd.DataFrame, reference_system: str
) -> pd.DataFrame:
    """Prognosefehler je ausgelöstem Fall ab dem Reset, gepaart gegen reference_system"""
    return _forecast_errors(window, SERIES_KEYS, reference_system).merge(
        cases[SERIES_KEYS + ["reset_day"]], on=SERIES_KEYS, how="left"
    )


def _pool_forecasts(window: pd.DataFrame, reference_system: str) -> pd.DataFrame:
    """Prognosefehler über alle ausgelösten Fälle, alle Tage ab dem Reset zusammen"""
    return _forecast_errors(
        window.assign(pool="alle"), ["pool"], reference_system, POOL_PAIR_KEYS
    )


def _forecast_weeks(
    window: pd.DataFrame,
    reference_system: str,
    llm_system: str,
    week_days: int,
    group: list[str],
) -> pd.DataFrame:
    """Je Woche ab dem Reset Tagesfehler beider Systeme, Differenz und Zahl der Fälle mit Tagen in dieser Woche, getrennt nach group (pool = alle ausgelösten Fälle zusammen, series = je Reihe, Cutover und Reihe = je Fall)"""
    weeks = add_weeks(window.assign(pool="alle"), week_days, "day_since_reset")
    keys = group + ["week"]
    errors = _forecast_errors(weeks, keys, reference_system, POOL_PAIR_KEYS)
    reference_rows = errors.loc[errors["config"].eq(reference_system)].set_index(keys)
    llm_rows = errors.loc[errors["config"].eq(llm_system)].set_index(keys)
    cases = (
        weeks[list(dict.fromkeys(SERIES_KEYS + keys))]
        .drop_duplicates()
        .groupby(keys)
        .size()
        .rename("cases")
    )

    return (
        pd.DataFrame(
            {
                "reference_day_error_w": reference_rows["mean_day_error_w"],
                "llm_day_error_w": llm_rows["mean_day_error_w"],
                "day_error_delta_w": llm_rows["mean_delta"],
                "cases": cases,
            }
        )
        .reset_index()
        .sort_values(keys)
        .reset_index(drop=True)
    )


def _count_notifications(days: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Je keys Tage, Meldungstage insgesamt und je Klasse, unknown-Tage und Meldungen je Zeitraum"""
    counts = count_notifications(
        days,
        keys,
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    )
    class_days = days[keys].copy()
    for classification in NOTIFICATION_CLASSIFICATIONS:
        class_days[f"{classification}_days"] = days["classification"].eq(classification)
    class_days = class_days.groupby(keys, as_index=False).sum()

    counts = counts.merge(class_days, on=keys)
    counts["notification_share_pct"] = (
        counts["notification_days"] / counts["days"] * 100
    )
    counts["unknown_share_pct"] = counts["unknown_days"] / counts["days"] * 100

    return counts[
        keys
        + ["days", "notification_days"]
        + [f"{classification}_days" for classification in NOTIFICATION_CLASSIFICATIONS]
        + ["unknown_days", "notifications_per_period"]
        + ["notification_share_pct", "unknown_share_pct"]
    ]


def _judge_cases(
    cases: pd.DataFrame,
    forecast: pd.DataFrame,
    notifications: pd.DataFrame,
    control: pd.DataFrame,
    *,
    reference_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Je Fall: LLM-System besser als Referenz = Tagesfehler belastbar kleiner oder weniger Meldungen, dazu die Resets im Kontrolllauf des Cutovers zur Ansicht"""
    forecast_delta = forecast.loc[
        forecast["config"].eq(llm_system),
        SERIES_KEYS + ["mean_delta", "exceeds_noise"],
    ].rename(
        columns={
            "mean_delta": "day_error_delta_w",
            "exceeds_noise": "day_error_reliable",
        }
    )
    rates = notifications.pivot(
        index=SERIES_KEYS, columns="config", values="notifications_per_period"
    ).reindex(columns=[reference_system, llm_system])
    notification_delta = (
        (rates[llm_system] - rates[reference_system])
        .rename("notification_delta")
        .reset_index()
    )
    control_resets = control.loc[control["config"].eq(llm_system)].set_index(
        "cutover_date"
    )["resets"]

    judged = cases.merge(forecast_delta, on=SERIES_KEYS, how="left").merge(
        notification_delta, on=SERIES_KEYS, how="left"
    )
    judged["control_resets"] = judged["cutover_date"].map(control_resets)
    judged["better"] = judged["triggered"] & (
        (judged["day_error_delta_w"].lt(0) & judged["day_error_reliable"].eq(True))
        | judged["notification_delta"].lt(0)
    )

    return judged


def _list_llm_answers(results: pd.DataFrame, outputs: pd.DataFrame) -> pd.DataFrame:
    answer_keys = ["scenario", "config", "analyzed_day"]
    days = results[
        answer_keys
        + ["series", "cutover_date", "days_since_cutover", "event", "adaption_action"]
    ]

    return (
        outputs.drop(columns=["decision_time", "evidence_paths"])
        .merge(days, on=answer_keys)
        .sort_values(SERIES_KEYS + ["days_since_cutover"])
        .reset_index(drop=True)
    )


def _summarize_overall(
    cases: pd.DataFrame,
    events_table: pd.DataFrame,
    pooled_forecast: pd.DataFrame,
    notifications: pd.DataFrame,
    control: pd.DataFrame,
    *,
    reference_system: str,
    llm_system: str,
) -> pd.DataFrame:
    """Je System die Hauptkennzahlen: Fälle mit Reset, Tagesfehler ab dem Reset und Meldungen je Zeitraum nach dem Reset (beide auf den Fällen, in denen das LLM-System zurückgesetzt hat), Resets im Kontrolllauf, dazu die Fälle, in denen das LLM-System besser war"""
    systems = [reference_system, llm_system]
    reset_cases = (
        events_table.groupby(["config"] + SERIES_KEYS)["reset_day"]
        .min()
        .notna()
        .groupby("config")
        .sum()
    )
    errors = (
        pooled_forecast.set_index("config")
        .assign(
            day_error_delta_two_se_w=lambda frame: 2 * frame["delta_standard_error"]
        )[
            [
                "mean_day_error_w",
                "mean_delta",
                "day_error_delta_two_se_w",
                "exceeds_noise",
                "paired_count",
            ]
        ]
        .rename(
            columns={
                "mean_day_error_w": "day_error_w",
                "mean_delta": "day_error_delta_w",
                "exceeds_noise": "day_error_reliable",
                "paired_count": "paired_days",
            }
        )
    )
    counts = notifications.groupby("config")[
        ["days", "notification_days", "unknown_days"]
    ].sum()
    rates = (
        counts["notification_days"] / counts["days"] * NOTIFICATION_PERIOD_DAYS
    ).rename("notifications_per_period")
    overall = (
        pd.DataFrame(
            {
                "triggered_cases": reset_cases,
                "control_resets": control.groupby("config")["resets"].sum(),
            }
        )
        .join(errors)
        .join(counts.rename(columns={"days": "notification_window_days"}))
        .join(rates)
        .reindex(systems)
    )
    overall["triggered_cases"] = overall["triggered_cases"].fillna(0)
    # Zeilen stehen als Referenz, LLM-System, die Differenz hat nur die zweite
    overall["notification_delta"] = overall["notifications_per_period"].diff()
    overall.loc[llm_system, "better_cases"] = cases["better"].sum()

    return overall.assign(cases=len(cases)).rename_axis("config").reset_index()


@dataclass(frozen=True)
class E3Summary:
    events: pd.DataFrame
    cases: pd.DataFrame
    overall: pd.DataFrame
    separations: pd.DataFrame
    control: pd.DataFrame
    forecast: pd.DataFrame
    forecast_weeks: pd.DataFrame
    forecast_weeks_by_series: pd.DataFrame
    forecast_weeks_by_case: pd.DataFrame
    notifications: pd.DataFrame
    notifications_weeks: pd.DataFrame
    notifications_weeks_pooled: pd.DataFrame
    notifications_weeks_by_series: pd.DataFrame
    latency: pd.DataFrame
    answers: pd.DataFrame
    interrupted: bool


def summarize_e3(
    results: pd.DataFrame,
    runtimes: pd.DataFrame,
    llm_outputs: pd.DataFrame,
    *,
    event_series: Mapping[str, tuple[tuple[int, str], ...]],
    reference_system: str,
    llm_system: str,
    week_days: int,
) -> E3Summary:
    """Alles, was der E3-Report zeigt"""
    event_list = list_event_series(event_series)
    results = results.assign(event=_assign_series_events(results, event_list))
    event_days = results.loc[results["event"].notna()].merge(
        event_list, on=["series", "event"]
    )
    systems = [reference_system, llm_system]

    separations = _find_separation_days(results)
    events_table = _summarize_events(event_days, event_list, separations)
    cases = _list_cases(events_table, llm_system)
    control = _summarize_control(results)
    window = _window_after_reset(results, cases, systems, include_reset_day=True)
    forecast = _compare_forecasts(window, cases, reference_system)
    after_reset = _window_after_reset(results, cases, systems, include_reset_day=False)
    after_weeks = add_weeks(after_reset, week_days, "day_since_reset")
    notifications = _count_notifications(after_reset, SERIES_KEYS + ["config"])
    cases = _judge_cases(
        cases,
        forecast,
        notifications,
        control,
        reference_system=reference_system,
        llm_system=llm_system,
    )

    return E3Summary(
        events=events_table,
        cases=cases,
        overall=_summarize_overall(
            cases,
            events_table,
            _pool_forecasts(window, reference_system),
            notifications,
            control,
            reference_system=reference_system,
            llm_system=llm_system,
        ),
        separations=separations,
        control=control,
        forecast=forecast,
        forecast_weeks=_forecast_weeks(
            window, reference_system, llm_system, week_days, ["pool"]
        ),
        forecast_weeks_by_series=_forecast_weeks(
            window, reference_system, llm_system, week_days, ["series"]
        ),
        forecast_weeks_by_case=_forecast_weeks(
            window, reference_system, llm_system, week_days, SERIES_KEYS
        ),
        notifications=notifications,
        notifications_weeks=_count_notifications(
            after_weeks, SERIES_KEYS + ["config", "week"]
        ),
        notifications_weeks_pooled=_count_notifications(
            after_weeks.assign(pool="alle"), ["pool", "config", "week"]
        ),
        notifications_weeks_by_series=_count_notifications(
            after_weeks, ["series", "config", "week"]
        ),
        latency=summarize_latency(
            results, runtimes, rule_system=reference_system, llm_system=llm_system
        ).merge(results[["scenario"] + SERIES_KEYS].drop_duplicates(), on="scenario"),
        answers=_list_llm_answers(results, llm_outputs),
        interrupted=bool(runtimes["interrupted"].any()),
    )
