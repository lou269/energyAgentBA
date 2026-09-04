import pandas as pd


def build_aggregated_data(
    canonical_data: pd.DataFrame,
    sample_period_seconds: int,
    min_coverage_share: float,
):
    data_15min, quality_15min = _aggregate(
        canonical_data,
        frequency="15min",
        sample_period_seconds=sample_period_seconds,
        min_coverage_share=min_coverage_share,
    )

    data_hourly, quality_hourly = _aggregate(
        canonical_data,
        frequency="1h",
        sample_period_seconds=sample_period_seconds,
        min_coverage_share=min_coverage_share,
    )

    return (
        data_15min,
        quality_15min,
        data_hourly,
        quality_hourly,
    )


def _aggregate(
    data: pd.DataFrame,
    frequency: str,
    sample_period_seconds: int,
    min_coverage_share: float,
):
    expected_count = int(
        pd.Timedelta(frequency).total_seconds() / sample_period_seconds
    )

    resampled = data.resample(frequency)

    aggregated = resampled.mean()
    valid_count = resampled.count()
    coverage_share = valid_count / expected_count
    coverage_mask = coverage_share >= min_coverage_share

    quality = pd.DataFrame(index=aggregated.index)

    for column in data.columns:
        quality[f"{column}_valid_observation_count"] = valid_count[column]
        quality[f"{column}_coverage_share"] = coverage_share[column]
        quality[f"{column}_coverage_mask"] = coverage_mask[column]

    return aggregated, quality