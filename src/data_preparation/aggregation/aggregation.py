from __future__ import annotations

import pandas as pd

from src.common.column_naming import channel_data_column
from src.common.timestamps import snap_to_local_midnight_range


def build_aggregated_data(
    channels: dict[str, pd.Series],
    sample_periods: dict[str, int],
    min_coverage_share: float,
):
    data_15min, quality_15min = _aggregate_channels(
        channels,
        sample_periods,
        frequency="15min",
        min_coverage_share=min_coverage_share,
    )

    data_hourly, quality_hourly = _aggregate_channels(
        channels,
        sample_periods,
        frequency="1h",
        min_coverage_share=min_coverage_share,
    )

    return (
        data_15min,
        quality_15min,
        data_hourly,
        quality_hourly,
    )


def _aggregate_channels(
    channels: dict[str, pd.Series],
    sample_periods: dict[str, int],
    frequency: str,
    min_coverage_share: float,
):
    aggregated_columns: dict[str, pd.Series] = {}
    quality_columns: dict[str, pd.Series] = {}

    for meter_key, series in channels.items():
        resampled = series.resample(frequency)
        valid_count = resampled.count()

        expected_count = pd.Timedelta(frequency).total_seconds() / sample_periods[meter_key]
        coverage_share = valid_count / expected_count

        aggregated_columns[meter_key] = resampled.mean()
        quality_columns[f"{meter_key}_valid_observation_count"] = valid_count
        quality_columns[f"{meter_key}_coverage_share"] = coverage_share
        quality_columns[f"{meter_key}_coverage_mask"] = coverage_share >= min_coverage_share

    aggregated = pd.DataFrame(aggregated_columns)
    quality = pd.DataFrame(quality_columns)

    return aggregated, quality


def build_canonical_data(
    data_15min: pd.DataFrame,
    quality_15min: pd.DataFrame,
    data_hourly: pd.DataFrame,
    quality_hourly: pd.DataFrame,
    meter_key: str,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    local_timezone: str,
):
  
    window_start, window_end = snap_to_local_midnight_range(window_start, window_end, local_timezone)

    quality_columns = [
        f"{meter_key}_valid_observation_count",
        f"{meter_key}_coverage_share",
        f"{meter_key}_coverage_mask",
    ]

    window_end_15min = window_end - pd.Timedelta(minutes=15)
    window_end_hourly = window_end - pd.Timedelta(hours=1)

    canonical_data_15min = data_15min.loc[window_start:window_end_15min, [meter_key]].rename(
        columns={meter_key: channel_data_column(meter_key, "15min")}
    )
    canonical_data_hourly = data_hourly.loc[window_start:window_end_hourly, [meter_key]].rename(
        columns={meter_key: channel_data_column(meter_key, "hourly")}
    )
    canonical_quality_15min = quality_15min.loc[window_start:window_end_15min, quality_columns]
    canonical_quality_hourly = quality_hourly.loc[window_start:window_end_hourly, quality_columns]

    return (
        window_start,
        window_end,
        canonical_data_15min,
        canonical_data_hourly,
        canonical_quality_15min,
        canonical_quality_hourly,
    )
