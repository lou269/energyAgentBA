from collections.abc import Sequence

import pandas as pd

from src.common.target_series import load_target_series
from src.common.timestamps import local_calendar_range


def build_decision_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    margin_before_days: int,
    margin_after_days: int,
    local_timezone: str,
) -> tuple[pd.Timestamp, ...]:
    start = window_start - pd.Timedelta(days=margin_before_days)
    end = window_end + pd.Timedelta(days=margin_after_days)

    return tuple(local_calendar_range(start, 24, end, local_timezone))


def crop_history_for_coldstart(
    series: pd.Series,
    *,
    coldstart_hours: int,
    first_decision_time: pd.Timestamp,
) -> pd.Series:
    
    crop_start = first_decision_time - pd.Timedelta(hours=coldstart_hours + 24)
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