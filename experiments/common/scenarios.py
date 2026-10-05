from collections.abc import Sequence
from functools import cache

import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE, PROJECT_CONFIG
from src.common.target_series import read_preprocessed_target
from src.common.timestamps import (
    local_calendar_range,
    local_midnight_utc,
    shift_local_days,
)
from src.pipeline.comparison_harness import ScenarioData
from src.pipeline.io import read_split_bounds


@cache
def load_target(split: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    # Mains, Imputationsmaske und Plausibilitätsflags des Fensters, in dem der Abschnitt liegt, je Fenster nur einmal gelesen
    return read_preprocessed_target(PROJECT_CONFIG, split)


def load_split_bounds(split: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    return read_split_bounds(PROJECT_CONFIG, split)


def build_decision_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    margin_before_days: int,
    margin_after_days: int,
) -> tuple[pd.Timestamp, ...]:
    start = shift_local_days(window_start, -margin_before_days, LOCAL_TIMEZONE)
    end = shift_local_days(window_end, margin_after_days, LOCAL_TIMEZONE)

    return tuple(local_calendar_range(start, 1, end, LOCAL_TIMEZONE))


def check_inside_split(
    series: pd.Series,
    split_bounds: tuple[pd.Timestamp, pd.Timestamp],
    first_time: pd.Timestamp,
    last_time: pd.Timestamp,
    history_start: pd.Timestamp | None,
) -> None:
    # die ausgewerteten Zeiten gehören in den Abschnitt, die Historie davor darf im Fenster davor liegen, aber nicht darüber hinaus
    split_start, split_end = split_bounds
    history_missing = history_start is not None and history_start < series.index[0]

    if first_time < split_start or last_time > split_end or history_missing:
        raise ValueError(
            f"{first_time} to {last_time} with history from {history_start} does not fit into the split {split_start} to {split_end}."
        )


def crop_history_for_coldstart(
    series: pd.Series,
    decision_times: tuple[pd.Timestamp, ...],
    coldstart_days: int,
    split_bounds: tuple[pd.Timestamp, pd.Timestamp],
) -> pd.Series:
    # der Tag vor dem ersten Entscheidungstag kommt im ersten Zyklus als new_observations und zählt zu den coldstart_days,
    # am ersten Entscheidungstag liegen also genau coldstart_days Tage vor, wie nach einem Reset
    crop_start = shift_local_days(decision_times[0], -coldstart_days, LOCAL_TIMEZONE)
    check_inside_split(
        series, split_bounds, decision_times[0], decision_times[-1], crop_start
    )

    return series.loc[crop_start:]


def scenario_without_calendar(
    target_series: pd.Series,
    decision_times: tuple[pd.Timestamp, ...],
    coldstart_days: int,
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
) -> ScenarioData:
    return ScenarioData(
        target_series=target_series,
        coldstart_days=coldstart_days,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=value_implausible,
    )


def local_day_window(start_date: str, days: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    # end ist die letzte Stunde des letzten Tages, passt also direkt in .loc
    start = local_midnight_utc(start_date, LOCAL_TIMEZONE)
    end = local_midnight_utc(
        start_date, LOCAL_TIMEZONE, days_offset=days
    ) - pd.Timedelta(hours=1)

    return start, end


def slice_history_window(
    target_series: pd.Series,
    target_imputed: pd.Series,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    history_days: int | None,
    split_bounds: tuple[pd.Timestamp, pd.Timestamp],
) -> tuple[pd.Series, pd.Series, pd.Series]:
    # history_days Tage Historie vor start, None = alles davor (K1 macro), ausgewertet wird start bis end inklusive
    history_start = (
        None
        if history_days is None
        else shift_local_days(start, -history_days, LOCAL_TIMEZONE)
    )
    check_inside_split(target_series, split_bounds, start, end, history_start)
    history = target_series.loc[history_start : start - pd.Timedelta(hours=1)]

    return history, target_series.loc[start:end], target_imputed.loc[start:end]


def subtract_channels_in_window(
    mains: pd.Series,
    appliance_data_hourly: pd.DataFrame,
    meter_keys: Sequence[str],
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.Series:
    window_mask = (mains.index >= window_start) & (mains.index < window_end)
    window_index = mains.index[window_mask]

    combined_load = (
        appliance_data_hourly.loc[:, meter_keys]
        .reindex(window_index)
        .fillna(0.0)
        .sum(axis=1)
    )

    adjusted = mains.copy()
    adjusted.loc[window_index] = (adjusted.loc[window_index] - combined_load).clip(
        lower=0.0
    )

    return adjusted
