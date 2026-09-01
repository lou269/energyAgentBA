import numpy as np
import pandas as pd


def build_multi_scale_analysis(
    train_data: pd.DataFrame,
    validation_data: pd.DataFrame,
    test_data: pd.DataFrame,
    target_column: str,
    *,
    short_term_window: int,
    sample_period_hours: float,
    long_term_window: int,
    min_daily_reference_samples: int,
    min_weekly_reference_samples: int,
    trend_threshold: float,
) -> pd.DataFrame:
    """Berechnet kausale Kurz-, Tages-, Wochen- und Langzeitvergleiche."""

    train_data = train_data.sort_index()
    validation_data = validation_data.sort_index()
    test_data = test_data.sort_index()
    
    splits = {
        "train": train_data,
        "validation": validation_data,
        "test": test_data,
    }

    for name, split_data in splits.items():
        if split_data.empty:
            raise ValueError(f"{name} split must not be empty.")
        if not split_data.index.is_unique:
            raise ValueError(f"{name} split contains duplicate timestamps.")

    if not (
        train_data.index.max() < validation_data.index.min()
        and validation_data.index.max() < test_data.index.min()
    ):
        raise ValueError(
            "Splits must be non-overlapping and ordered: "
            "train < validation < test."
        )

    data = pd.concat([train_data, validation_data, test_data])

    train_index = pd.DatetimeIndex(train_data.index)
    data_index = pd.DatetimeIndex(data.index)

    result = pd.DataFrame(index=data.index)

    result["split"] = pd.NA
    result.loc[train_data.index, "split"] = "train"
    result.loc[validation_data.index, "split"] = "validation"
    result.loc[test_data.index, "split"] = "test"

    result["current_power"] = data[target_column]

    previous_power = result["current_power"].shift(1)

    result["short_term_mean"] = previous_power.rolling(
        window=short_term_window,
        min_periods=short_term_window,
    ).mean()

    result["long_term_mean"] = previous_power.rolling(
        window=long_term_window,
        min_periods=long_term_window,
    ).mean()
    
    trend_time = np.arange(short_term_window) * sample_period_hours
    centered_trend_time = trend_time - trend_time.mean()
    trend_denominator = np.square(centered_trend_time).sum()

    result["trend_slope_w_per_hour"] = previous_power.rolling(
        window=short_term_window,
        min_periods=short_term_window,
    ).apply(
        lambda values: (
            np.dot(values, centered_trend_time) / trend_denominator
        ),
        raw=True,
    )

    train_reference = pd.DataFrame(
        {
            "power": train_data[target_column],
            "hour": train_index.hour,
            "minute": train_index.minute,
            "day_of_week": train_index.dayofweek,
        },
        index=train_data.index,
    )

    daily_profile = train_reference.groupby(
        ["hour", "minute"]
    )["power"].agg(["mean", "count"])

    daily_profile.loc[
        daily_profile["count"] < min_daily_reference_samples,
        "mean",
    ] = np.nan

    daily_keys = pd.MultiIndex.from_arrays(
        [data_index.hour, data_index.minute],
        names=["hour", "minute"],
    )

    result["daily_expected"] = daily_profile["mean"].reindex(
        daily_keys
    ).to_numpy()

    train_daily_expected = (
        train_reference.groupby(["hour", "minute"])["power"]
        .transform(
            lambda values: values.shift(1).expanding(
                min_periods=min_daily_reference_samples
            ).mean()
        )
    )

    result.loc[train_data.index, "daily_expected"] = train_daily_expected

    weekly_profile = train_reference.groupby(
        ["day_of_week", "hour", "minute"]
    )["power"].agg(["mean", "count"])

    weekly_profile.loc[
        weekly_profile["count"] < min_weekly_reference_samples,
        "mean",
    ] = np.nan

    weekly_keys = pd.MultiIndex.from_arrays(
        [
            data_index.dayofweek,
            data_index.hour,
            data_index.minute,
        ],
        names=["day_of_week", "hour", "minute"],
    )

    result["weekly_expected"] = weekly_profile["mean"].reindex(
        weekly_keys
    ).to_numpy()

    train_weekly_expected = (
        train_reference.groupby(
            ["day_of_week", "hour", "minute"]
        )["power"]
        .transform(
            lambda values: values.shift(1).expanding(
                min_periods=min_weekly_reference_samples
            ).mean()
        )
    )

    result.loc[train_data.index, "weekly_expected"] = train_weekly_expected

    daily_reference = result["daily_expected"].where(
        result["daily_expected"].ne(0)
    )
    weekly_reference = result["weekly_expected"].where(
        result["weekly_expected"].ne(0)
    )
    short_term_reference = result["short_term_mean"].where(
        result["short_term_mean"].ne(0)
    )
    long_term_reference = result["long_term_mean"].where(
        result["long_term_mean"].ne(0)
    )

    result["short_term_deviation"] = (
        result["current_power"] - short_term_reference
    ) / short_term_reference

    result["daily_deviation"] = (
        result["current_power"] - daily_reference
    ) / daily_reference

    result["weekly_deviation"] = (
        result["current_power"] - weekly_reference
    ) / weekly_reference

    result["long_term_deviation"] = (
        result["current_power"] - long_term_reference
    ) / long_term_reference

    result["level_change"] = (
        result["short_term_mean"] - long_term_reference
    ) / long_term_reference

    trend_window_hours = short_term_window * sample_period_hours

    result["trend_change"] = (
        result["trend_slope_w_per_hour"] * trend_window_hours
    ) / short_term_reference

    result["trend"] = "stable"

    result.loc[
        result["trend_change"] > trend_threshold,
        "trend",
    ] = "increasing"

    result.loc[
        result["trend_change"] < -trend_threshold,
        "trend",
    ] = "decreasing"

    result.loc[
        result["trend_change"].isna(),
        "trend",
    ] = pd.NA

    result.index.name = "timestamp"

    return result