from dataclasses import dataclass

import numpy as np
import pandas as pd

from experiments.common.evaluation import (
    add_gate_flags,
    count_notifications,
    local_dates,
    summarize_paired_differences,
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


# Spalten aus anomaly.csv, an denen sich ablesen lässt, wie weit der Urlaub von den Schwellen entfernt ist
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
]

PHASES = ("before", "absence", "after_return")


def by_phase(column: pd.Series) -> pd.Series:
    # Schlüssel für sort_values: Phasen in zeitlicher statt alphabetischer Reihenfolge
    return column.map(PHASES.index) if column.name == "phase" else column


def label_absence_days(
    comparison: pd.DataFrame,
    anomaly: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    target_classification: str,
    absence_event_id: str,
) -> pd.DataFrame:
    start_day, end_day = local_dates([window_start, window_end])
    days = add_gate_flags(
        comparison.merge(
            anomaly[["config", "analyzed_day"] + PRECHECK_ANOMALY_COLUMNS],
            on=["config", "analyzed_day"],
            how="left",
        )
    )
    analyzed = pd.to_datetime(days["analyzed_day"])
    target = days["classification"].eq(target_classification)
    supported = target & days["adaption_reason"].fillna("").str.contains(
        absence_event_id, regex=False
    )

    return days.assign(
        phase=np.select(
            [analyzed < start_day, analyzed < end_day], PHASES[:2], PHASES[2]
        ),
        absence_day=(analyzed - start_day).dt.days,
        drift_gate=days["sustained_drift"].eq(True),
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
        new_pattern_days=("new_pattern", "sum"),
        low_days=("low", "sum"),
        peak_days=("peak", "sum"),
        absence_classified_days=("absence_classified", "sum"),
        reset_days=("reset", "sum"),
        failed_days=("failed", "sum"),
        mean_mae_w=("mae_w", "mean"),
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
    forecast: pd.DataFrame
    timeline: pd.DataFrame
    reduction: pd.DataFrame
    mean_reduction_w: float
    first_analyzed_day: str
    last_analyzed_day: str


def summarize_e2(
    comparison: pd.DataFrame,
    anomaly: pd.DataFrame,
    calendar_availability: pd.DataFrame,
    forecasts: pd.DataFrame,
    reduction: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    target_classification: str,
    absence_event_id: str,
    reference_config: str,
) -> E2Summary:
    days = label_absence_days(
        comparison,
        anomaly,
        window_start=window_start,
        window_end=window_end,
        target_classification=target_classification,
        absence_event_id=absence_event_id,
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

    calendar_use = (
        calendar_availability.merge(
            days[["config", "analyzed_day", "phase"]], on=["config", "analyzed_day"]
        )
        .groupby(["config", "phase"], as_index=False)
        .agg(
            classified_days=("calendar_available", "size"),
            calendar_days=("calendar_available", "sum"),
        )
    )

    # gepaart am selben Tag, so zählen nur Tage, die beide Systeme haben
    paired = pd.concat(
        [
            summarize_paired_differences(
                phase_days.pivot(
                    index="analyzed_day", columns="config", values="mae_w"
                ),
                reference_config,
            ).assign(phase=phase)
            for phase, phase_days in days.groupby("phase")
        ],
        ignore_index=True,
    ).rename(columns={"variant": "config"})
    forecast = (
        days.groupby(["config", "phase"], as_index=False)
        .agg(mean_mae_w=("mae_w", "mean"))
        .merge(paired, on=["config", "phase"], how="left")
        .sort_values(["config", "phase"], key=by_phase)
        .reset_index(drop=True)
    )

    # je Kalendertag: Ist aus today_mean (für jede Config derselbe Tag), Prognose als Tagesmittel für diesen Tag, dazu die Einordnung dieses Tages, die am Folgetag getroffen wird
    actual_w = days.groupby("analyzed_day")["today_mean"].first()
    forecast_w = forecasts.groupby(["config", "forecast_day"])["y_pred"].mean()
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
        forecast=forecast,
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
) -> GatePrecheckSummary:
    days = label_absence_days(
        comparison,
        anomaly,
        window_start=window_start,
        window_end=window_end,
        target_classification=target_classification,
        absence_event_id=absence_event_id,
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
            + ["classification", "adaption_action", "mae_w"]
        ]
        .sort_values(["config", "absence_day"])
        .reset_index(drop=True),
    )
