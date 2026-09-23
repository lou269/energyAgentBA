from collections.abc import Sequence

import pandas as pd

from src.common.target_series import load_target_series
from src.common.timestamps import local_calendar_range, shift_local_days


def build_decision_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    margin_before_days: int,
    margin_after_days: int,
    local_timezone: str,
) -> tuple[pd.Timestamp, ...]:
    start = shift_local_days(window_start, -margin_before_days, local_timezone)
    end = shift_local_days(window_end, margin_after_days, local_timezone)

    return tuple(local_calendar_range(start, 1, end, local_timezone))


def crop_history_for_coldstart(
    series: pd.Series,
    *,
    coldstart_days: int,
    first_decision_time: pd.Timestamp,
    local_timezone: str,
) -> pd.Series:
    # coldstart_days Historie plus der Tag vor first_decision_time, der im ersten Zyklus als new_observations kommt
    crop_start = shift_local_days(first_decision_time, -(coldstart_days + 1), local_timezone)
    return series.loc[crop_start:]


def subtract_channels_in_window(
    mains: pd.Series,
    appliance_data_hourly: pd.DataFrame,
    meter_keys: Sequence[str],
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.Series:
    if not meter_keys:
        raise ValueError("meter_keys must not be empty.")

    missing = set(meter_keys) - set(appliance_data_hourly.columns)
    if missing:
        raise ValueError(f"appliance_data_hourly is missing columns: {', '.join(sorted(missing))}")

    window_mask = (mains.index >= window_start) & (mains.index < window_end)
    window_index = mains.index[window_mask]

    combined_load = (
        appliance_data_hourly.loc[:, meter_keys]
        .reindex(window_index)
        .fillna(0.0)
        .sum(axis=1)
    )

    adjusted = mains.copy()
    adjusted.loc[window_index] = (adjusted.loc[window_index] - combined_load).clip(lower=0.0)

    return adjusted

def add_constant_step(series: pd.Series, start: pd.Timestamp, watts: float) -> pd.Series:
    stepped = series.copy()
    stepped.loc[stepped.index >= start] += watts

    return stepped


def scale_from(series: pd.Series, start: pd.Timestamp, factor: float) -> pd.Series:
    scaled = series.copy()
    scaled.loc[scaled.index >= start] *= factor

    return scaled

