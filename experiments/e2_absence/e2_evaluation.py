from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    count_notifications,
    local_dates,
    summarize_classification_detection,
    summarize_mae_before_after,
)
from experiments.common.standard_config import (
    NOTIFICATION_CLASSIFICATIONS,
    NOTIFICATION_PERIOD_DAYS,
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


@dataclass(frozen=True)
class E2Summary:
    detection: pd.DataFrame
    forecast: pd.DataFrame
    reduction: pd.DataFrame
    mean_reduction_w: float
    first_analyzed_day: str
    last_analyzed_day: str


def summarize_e2(
    comparison: pd.DataFrame,
    reduction: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    target_classification: str,
) -> E2Summary:
    """Alles, was der E2-Report zeigt: Erkennung der Abwesenheit, Prognose vor/ab Beginn, Absenkung durch das Herausrechnen"""
    mae = summarize_mae_before_after(comparison, window_start).pivot(
        index="config", columns="period", values="mean_mae_w"
    )

    return E2Summary(
        detection=summarize_classification_detection(
            comparison, window_start, target_classification
        ),
        forecast=pd.DataFrame(
            {"mae_before_w": mae["before_event"], "mae_after_w": mae["after_event"]}
        ).reset_index(),
        reduction=reduction,
        mean_reduction_w=reduction["reduction_w"].mean(),
        first_analyzed_day=comparison["analyzed_day"].min(),
        last_analyzed_day=comparison["analyzed_day"].max(),
    )


# Spalten aus anomaly.csv, an denen sich ablesen lässt, wie weit der Urlaub von den Schwellen entfernt ist
PRECHECK_ANOMALY_COLUMNS = [
    "today_mean",
    "weekday_expected",
    "daily_score",
    "weekday_score",
    "weekly_score",
    "long_term_score",
    "weekly_anomaly_streak_days",
    "long_term_anomaly_streak_days",
    "anomaly_level",
    "sustained_drift",
]


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
) -> GatePrecheckSummary:
    """Öffnet der Urlaub das Gate, über welchen Pfad (Einzeltag oder Drift) und ab welchem Urlaubstag, je Config und Phase. Urlaubstag 0 = erster Tag der Abwesenheit"""
    start_day, end_day = local_dates([window_start, window_end])
    days = comparison.merge(
        anomaly[["config", "analyzed_day"] + PRECHECK_ANOMALY_COLUMNS],
        on=["config", "analyzed_day"],
        how="left",
    )
    analyzed = pd.to_datetime(days["analyzed_day"])
    single_day_gate = days["anomaly_level"].isin(["unusual", "strong_anomaly"])
    drift_gate = days["sustained_drift"].eq(True)

    days = days.assign(
        phase=np.select(
            [analyzed < start_day, analyzed < end_day],
            ["before", "absence"],
            "after_return",
        ),
        absence_day=(analyzed - start_day).dt.days,
        single_day_gate=single_day_gate,
        drift_gate=drift_gate,
        gate_open=single_day_gate | drift_gate,
        reset=days["adaption_action"].eq("advance_history_start"),
        new_pattern=days["classification"].eq("new_pattern"),
        low=days["classification"].eq("low"),
        peak=days["classification"].eq("peak"),
    )

    phases = days.groupby(["config", "phase"], as_index=False).agg(
        days=("phase", "size"),
        gate_open_days=("gate_open", "sum"),
        single_day_gate_days=("single_day_gate", "sum"),
        drift_gate_days=("drift_gate", "sum"),
        new_pattern_days=("new_pattern", "sum"),
        low_days=("low", "sum"),
        peak_days=("peak", "sum"),
        reset_days=("reset", "sum"),
        mean_mae_w=("mae_w", "mean"),
    )
    notifications = count_notifications(
        days,
        ["config", "phase"],
        notification_classes=NOTIFICATION_CLASSIFICATIONS,
        period_days=NOTIFICATION_PERIOD_DAYS,
    )
    phases = phases.merge(
        notifications[["config", "phase", "notification_days"]],
        on=["config", "phase"],
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
        phases=phases,
        first_days=first_days.astype("Int64").reset_index(),
        days_from_absence=from_absence[
            ["config", "absence_day", "analyzed_day", "phase"]
            + PRECHECK_ANOMALY_COLUMNS
            + ["classification", "adaption_action", "mae_w"]
        ]
        .sort_values(["config", "absence_day"])
        .reset_index(drop=True),
    )
