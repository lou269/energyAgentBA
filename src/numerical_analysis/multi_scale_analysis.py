import math

import numpy as np
import pandas as pd

from src.common.timestamps import local_day


def build_multi_scale_analysis(
    history: pd.Series,
    *,
    reference_window_end: pd.Timestamp,
    reference_window_rolling_days: int | None,
    short_term_window: int,
    sample_period_hours: float,
    long_term_window: int,
    weekly_window_days: int,
    min_weekday_reference_samples: int,
    trend_threshold: float,
    min_reference_power_w: float,
    rolling_window_min_coverage: float,
    local_timezone: str,
) -> pd.DataFrame:
    local_history = history.tz_convert(local_timezone)

    daily_mean = local_history.resample("D").mean()
    daily_std = local_history.resample("D").std(ddof=0)

    # der Tag von reference_window_end ist evtl. nur teilweise beobachtet -> ganz raus aus dem Training, fällt stattdessen unter validation
    reference_day = local_day(reference_window_end, local_timezone)

    train_index = daily_mean.index[daily_mean.index < reference_day]
    remaining_index = daily_mean.index[daily_mean.index >= reference_day]

    if reference_window_rolling_days is not None:
        # n Kalendertage, auch über eine Zeitumstellung, ältere Tage zählen nur noch für weekly_mean/long_term_window_mean
        train_index = train_index[-reference_window_rolling_days:]

    if len(remaining_index) < 2:
        raise ValueError("Not enough observed days after the reference window to score validation and test.")

    result = pd.DataFrame(index=daily_mean.index)

    result["split"] = pd.NA
    result.loc[train_index, "split"] = "train"
    result.loc[remaining_index[:-1], "split"] = "validation"
    result.loc[remaining_index[-1:], "split"] = "test"

    result["today_mean"] = daily_mean

    previous_power = result["today_mean"].shift(1)

    result["trend_reference_mean"] = previous_power.rolling(
        window=short_term_window, min_periods=short_term_window
    ).mean()

    # min_periods < window, damit ein einzelner NaN-Tag (z.B. measurement_error) im Fenster nicht die komplette Skala für long_term_window Tage lahmlegt
    long_term_min_periods = math.ceil(long_term_window * rolling_window_min_coverage)
    result["long_term_window_mean"] = result["today_mean"].rolling(window=long_term_window, min_periods=long_term_min_periods).mean()

    trend_time = np.arange(short_term_window) * sample_period_hours
    centered_trend_time = trend_time - trend_time.mean()
    trend_denominator = np.square(centered_trend_time).sum()

    result["trend_slope_w_per_hour"] = previous_power.rolling(
        window=short_term_window, min_periods=short_term_window
    ).apply(
        lambda values: np.dot(values, centered_trend_time) / trend_denominator,
        raw=True,
    )

    train_reference = pd.DataFrame(
        {
            "power": daily_mean.loc[train_index],
            "day_of_week": pd.DatetimeIndex(train_index).dayofweek,
        },
        index=train_index,
    )

    weekday_profile = train_reference.groupby("day_of_week")["power"].agg(["mean", "count"])
    weekday_profile.loc[weekday_profile["count"] < min_weekday_reference_samples, "mean"] = np.nan

    weekday_keys = pd.DatetimeIndex(daily_mean.index).dayofweek
    result["weekday_expected"] = weekday_profile["mean"].reindex(weekday_keys).to_numpy()

    train_weekday_expected = train_reference.groupby("day_of_week")["power"].transform(
        lambda values: values.shift(1).expanding(min_periods=min_weekday_reference_samples).mean()
    )

    result.loc[train_index, "weekday_expected"] = train_weekday_expected

    weekday_reference = result["weekday_expected"].where(result["weekday_expected"].abs() >= min_reference_power_w)
    trend_reference = result["trend_reference_mean"].where(result["trend_reference_mean"].abs() >= min_reference_power_w)

    result["weekday_deviation"] = (result["today_mean"] - weekday_reference) / weekday_reference

    trend_window_hours = short_term_window * sample_period_hours

    result["trend_change"] = (result["trend_slope_w_per_hour"] * trend_window_hours) / trend_reference

    result["trend"] = "stable"

    result.loc[result["trend_change"] > trend_threshold, "trend"] = "increasing"

    result.loc[result["trend_change"] < -trend_threshold, "trend"] = "decreasing"

    result.loc[result["trend_change"].isna(), "trend"] = pd.NA

    result["daily_std"] = daily_std
    result["daily_std_expected"] = _walk_forward_expectation(daily_std, train_index, remaining_index)

    result["today_mean_expected"] = _walk_forward_expectation(daily_mean, train_index, remaining_index)

    weekly_min_periods = math.ceil(weekly_window_days * rolling_window_min_coverage)
    result["weekly_mean"] = result["today_mean"].rolling(window=weekly_window_days, min_periods=weekly_min_periods).mean()
    result["weekly_mean_expected"] = _walk_forward_expectation(result["weekly_mean"], train_index, remaining_index)

    result["long_term_expected"] = _walk_forward_expectation(result["long_term_window_mean"], train_index, remaining_index)

    result.index.name = "timestamp"

    return result


def _walk_forward_expectation(
    values: pd.Series,
    train_index: pd.Index,
    remaining_index: pd.Index,
) -> pd.Series:
    # in train expandierend nur über frühere Tage (kein Blick nach vorn), für validation/test auf den train-Mittelwert eingefroren
    expected = pd.Series(np.nan, index=values.index)
    expected.loc[train_index] = values.loc[train_index].shift(1).expanding(min_periods=1).mean()
    expected.loc[remaining_index] = values.loc[train_index].mean()

    return expected