from __future__ import annotations

import pandas as pd


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
