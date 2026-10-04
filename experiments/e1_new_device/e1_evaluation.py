from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    compare_mae_to_reference,
    compare_mae_to_reference_after_reset,
    count_days_by_period,
    list_decision_events,
    summarize_mae_before_after,
)
from experiments.common.standard_config import COLDSTART_DAYS, LOCAL_TIMEZONE
from experiments.e1_new_device.e1_config import E1Config
from src.common.timestamps import local_calendar_range, local_day, shift_local_days


def _by_period(counts: pd.DataFrame, configs: list[str]) -> pd.DataFrame:
    return counts.pivot(index="config", columns="period").reindex(configs)


def summarize_detection(
    counts: pd.DataFrame,
    control_counts: pd.DataFrame | None,
    events: pd.DataFrame,
    *,
    target_classification: str,
    configs: list[str],
) -> pd.DataFrame:
    days = _by_period(counts, configs)
    after_event = events.loc[events["day_since_event"].ge(FIRST_ANALYZED_DAY)]
    hits = after_event.loc[after_event["classification"].eq(target_classification)]
    resets = after_event.loc[after_event["adaption_action"].eq("advance_history_start")]

    detection = pd.DataFrame(index=configs)
    detection["first_detection_day"] = hits.groupby("config")["day_since_event"].min()
    detection["target_days_after"] = days.get((target_classification, "after_event"), 0)
    detection["false_alarm_days_before"] = days.get(
        (target_classification, "before_event"), 0
    )
    if control_counts is not None:
        control_days = _by_period(control_counts, configs)
        detection["control_target_days_after"] = control_days.get(
            (target_classification, "after_event"), 0
        )
    detection["adaptions_before"] = days[("adaption_days", "before_event")]
    detection["adaptions_after"] = days[("adaption_days", "after_event")]
    detection["first_reset_day"] = resets.groupby("config")["day_since_event"].min()

    return detection.astype("Int64").rename_axis("config").reset_index()


def _combine_classification_counts(
    counts: pd.DataFrame, control_counts: pd.DataFrame | None, configs: list[str]
) -> pd.DataFrame:
    # Tage je Klassifikation vor und ab Cutover, dazu ab Cutover im Kontrolllauf
    frames = [counts]
    if control_counts is not None:
        control_after = control_counts.loc[control_counts["period"].eq("after_event")]
        frames.append(control_after.assign(period="after_event_control"))

    table = pd.concat(frames, ignore_index=True)
    table = table.loc[table["config"].isin(configs)].fillna(0)
    table["period"] = pd.Categorical(
        table["period"], ["before_event", "after_event", "after_event_control"]
    )
    table = table.sort_values(["config", "period"])

    classifications = [
        column
        for column in table.columns
        if column not in ("config", "period", "days", "adaption_days", "failed_days")
    ]
    counted = table[["days"] + classifications + ["failed_days"]].astype("Int64")

    return pd.concat([table[["config", "period"]], counted], axis=1).reset_index(
        drop=True
    )


@dataclass(frozen=True)
class E1Summary:
    detection: pd.DataFrame
    # ab Cutover vermischt Tage vor und nach dem Eingriff, hier nur die Tage ab dem Reset
    after_reset: pd.DataFrame
    forecast: pd.DataFrame
    classifications: pd.DataFrame
    events: pd.DataFrame
    failed: pd.DataFrame
    no_reset: bool
    first_analyzed_day: str
    last_analyzed_day: str
    days_before: int
    days_after: int


def summarize_e1(
    comparison: pd.DataFrame,
    control_comparison: pd.DataFrame | None,
    *,
    cutover_time: pd.Timestamp,
    reference_config: str,
    target_classification: str,
) -> E1Summary:
    """Alles, was der E1-Report zeigt: Erkennung, Prognose vor/ab Cutover und ab Reset, Klassifikationen, Ereignisse"""
    configs = sorted(
        comparison.loc[comparison["classification"].notna(), "config"].unique()
    )

    counts = count_days_by_period(comparison, cutover_time)
    events = list_decision_events(comparison, cutover_time, target_classification)
    mae = summarize_mae_before_after(comparison, cutover_time).pivot(
        index="config", columns="period", values="mean_mae_w"
    )
    forecast = pd.DataFrame(
        {"mae_before_w": mae["before_event"], "mae_after_w": mae["after_event"]}
    )

    control_counts = None
    if control_comparison is not None:
        control_counts = count_days_by_period(control_comparison, cutover_time)
        # ab Cutover sind Haupt- und Kontrollreihe identisch, nur das Modell hat die Geräte vorher nie gesehen
        control_mae = summarize_mae_before_after(
            control_comparison, cutover_time
        ).pivot(index="config", columns="period", values="mean_mae_w")
        forecast["control_mae_after_w"] = control_mae["after_event"]

    forecast = forecast.join(
        compare_mae_to_reference(comparison, cutover_time, reference_config).set_index(
            "config"
        )
    )
    detection = summarize_detection(
        counts,
        control_counts,
        events,
        target_classification=target_classification,
        configs=configs,
    )
    failed = counts.groupby("config", as_index=False)[["failed_days", "days"]].sum()
    reference_days = counts.loc[counts["config"].eq(reference_config)].set_index(
        "period"
    )["days"]

    return E1Summary(
        detection=detection,
        after_reset=compare_mae_to_reference_after_reset(
            comparison, cutover_time, reference_config
        ),
        forecast=forecast,
        classifications=_combine_classification_counts(counts, control_counts, configs),
        events=events,
        failed=failed.loc[failed["failed_days"] > 0],
        no_reset=bool(detection["first_reset_day"].isna().all()),
        first_analyzed_day=comparison["analyzed_day"].min(),
        last_analyzed_day=comparison["analyzed_day"].max(),
        days_before=reference_days["before_event"],
        days_after=reference_days["after_event"],
    )


# Geräte- und Cutover-Wahl für e1_device_check, läuft in nilmtk-env


def candidate_cutover_times(
    window_start: pd.Timestamp,
    split_start: pd.Timestamp,
    split_end: pd.Timestamp,
    e1_config: E1Config,
) -> pd.DatetimeIndex:
    first_decision = max(
        split_start, shift_local_days(window_start, COLDSTART_DAYS, LOCAL_TIMEZONE)
    )
    first = shift_local_days(
        local_day(first_decision, LOCAL_TIMEZONE),
        e1_config.margin_before_days,
        LOCAL_TIMEZONE,
    )
    last = shift_local_days(
        local_day(split_end, LOCAL_TIMEZONE),
        -e1_config.margin_after_days,
        LOCAL_TIMEZONE,
    )

    return local_calendar_range(
        first, e1_config.cutover_step_days, last, LOCAL_TIMEZONE
    )


def summarize_cutover_windows(
    device_hourly: pd.Series,
    coverage_mask: pd.Series,
    mains_hourly: pd.Series,
    cutover_times: pd.DatetimeIndex,
    window_days: int,
) -> pd.DataFrame:
    rows = []

    for cutover_time in cutover_times:
        window = slice(
            cutover_time,
            shift_local_days(cutover_time, window_days, LOCAL_TIMEZONE)
            - pd.Timedelta(hours=1),
        )
        rows.append(
            {
                "cutover_date": cutover_time.tz_convert(LOCAL_TIMEZONE)
                .date()
                .isoformat(),
                "device_mean_w": device_hourly.loc[window].mean(),
                # wie activity_share im Ranking, nur auf das Fenster nach dem Cutover beschränkt
                "device_share": device_hourly.loc[window].sum()
                / mains_hourly.loc[window].sum(),
                "device_coverage": coverage_mask.loc[window].mean(),
            }
        )

    return pd.DataFrame(rows)


def select_cutover(windows: pd.DataFrame, min_device_coverage: float) -> pd.DataFrame:
    # bei Lücken im Gerätekanal wäre der Anteil zu niedrig und das Herausrechnen vor dem Cutover unvollständig
    covered = windows.loc[windows["device_coverage"] >= min_device_coverage]

    return windows.assign(selected=windows.index == covered["device_share"].idxmax())
