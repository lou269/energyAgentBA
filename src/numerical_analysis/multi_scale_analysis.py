import math
from collections.abc import Sequence
from typing import cast

import numpy as np
import pandas as pd

from src.common.timestamps import local_daily_mean


def build_multi_scale_analysis(
    history: pd.Series,
    *,
    analyzed_day: pd.Timestamp,
    reference_window_rolling_days: int,
    short_term_window: int,
    sample_period_hours: float,
    long_term_window: int,
    long_term_reference_days: int,
    weekly_window_days: int,
    min_weekday_reference_samples: int,
    min_longterm_reference_samples: int,
    trend_threshold: float,
    min_reference_power_w: float,
    rolling_window_min_coverage: float,
    robust_scales: Sequence[str],
    local_timezone: str,
) -> pd.DataFrame:
    local_history = history.tz_convert(local_timezone)
    daily_mean = local_daily_mean(history, local_timezone)
    daily_std = local_history.resample("D").std(ddof=0)

    analyzed_position = cast(int, daily_mean.index.get_loc(analyzed_day))

    result = pd.DataFrame(index=daily_mean.index)
    result["today_mean"] = daily_mean
    result["daily_std"] = daily_std

    previous_power = result["today_mean"].shift(1)

    result["trend_daily_mean"] = previous_power.rolling(
        window=short_term_window, min_periods=short_term_window
    ).mean()

    trend_time = np.arange(short_term_window) * sample_period_hours
    centered_trend_time = trend_time - trend_time.mean()
    trend_denominator = np.square(centered_trend_time).sum()

    result["trend_slope_w_per_hour"] = previous_power.rolling(
        window=short_term_window, min_periods=short_term_window
    ).apply(
        lambda values: np.dot(values, centered_trend_time) / trend_denominator,
        raw=True,
    )

    trend_reference = result["trend_daily_mean"].where(
        result["trend_daily_mean"].abs() >= min_reference_power_w
    )
    trend_window_hours = short_term_window * sample_period_hours
    result["trend_change"] = (
        result["trend_slope_w_per_hour"] * trend_window_hours
    ) / trend_reference

    result["trend"] = "stable"
    result.loc[result["trend_change"] > trend_threshold, "trend"] = "increasing"
    result.loc[result["trend_change"] < -trend_threshold, "trend"] = "decreasing"
    result.loc[result["trend_change"].isna(), "trend"] = pd.NA

    # Erwartung und Referenz gelten für analyzed_day, die Spalten tragen sie in jeder Zeile
    # Tagesskalen: Referenz sind die Tage vor dem eingeordneten Tag
    day_window = _reference_window(
        analyzed_position - 1,
        rolling_days=reference_window_rolling_days,
    )
    daily_robust = "daily" in robust_scales
    day_mean_reference = _only_positions(daily_mean, day_window)

    result["daily_reference_value"] = _only_positions(daily_std, day_window)
    result["daily_std_expected"] = _center(
        result["daily_reference_value"], robust=daily_robust
    )
    # nur für die Richtung von daily, gleiche Mitte wie die Skala selbst
    result["today_mean_expected"] = _center(day_mean_reference, robust=daily_robust)

    result["weekday_reference_value"] = day_mean_reference
    result["weekday_expected"] = _weekday_expected(
        day_mean_reference,
        min_samples=min_weekday_reference_samples,
        robust="weekday" in robust_scales,
    )

    # Rollmittel: Beobachtung auf der vollen Reihe
    weekly_min_periods = math.ceil(weekly_window_days * rolling_window_min_coverage)
    result["weekly_mean"] = daily_mean.rolling(
        window=weekly_window_days, min_periods=weekly_min_periods
    ).mean()
    result["weekly_reference_value"] = _weekly_reference(
        result["weekly_mean"],
        analyzed_position=analyzed_position,
        weekly_window_days=weekly_window_days,
        rolling_days=reference_window_rolling_days,
    )
    result["weekly_mean_expected"] = _center(
        result["weekly_reference_value"], robust="weekly" in robust_scales
    )

    long_term_min_periods = math.ceil(long_term_window * rolling_window_min_coverage)
    result["long_term_window_mean"] = daily_mean.rolling(
        window=long_term_window, min_periods=long_term_min_periods
    ).mean()
    # je Tag das Mittel der long_term_reference_days direkt vor dessen Beobachtungsfenster
    result["long_term_expected"] = (
        daily_mean.rolling(
            window=long_term_reference_days,
            min_periods=min_longterm_reference_samples,
        )
        .mean()
        .shift(long_term_window)
    )

    for scale, observed_column, expected_column in (
        ("weekday", "today_mean", "weekday_expected"),
        ("weekly", "weekly_mean", "weekly_mean_expected"),
        ("long_term", "long_term_window_mean", "long_term_expected"),
    ):
        result[f"{scale}_deviation_pct"] = _deviation_pct(
            result[observed_column], result[expected_column], min_reference_power_w
        )

    result.index.name = "timestamp"

    return result


def expected_weekday_mean(
    history: pd.Series,
    forecast_day: pd.Timestamp,
    *,
    reference_window_rolling_days: int,
    min_weekday_reference_samples: int,
    robust: bool,
    local_timezone: str,
) -> float | None:
    # wie weekday_expected oben, nur für einen Tag, der noch nicht in history liegt
    daily_mean = local_daily_mean(history, local_timezone)
    reference = daily_mean.iloc[-reference_window_rolling_days:]
    with_day = pd.concat([reference, pd.Series([np.nan], index=[forecast_day])])
    expected = _weekday_expected(
        with_day, min_samples=min_weekday_reference_samples, robust=robust
    ).iloc[-1]

    return None if pd.isna(expected) else float(expected)


def _deviation_pct(
    measured: pd.Series,
    expected: pd.Series,
    min_reference_power_w: float,
) -> pd.Series:
    # bei fast null Watt Referenz wird die Prozentzahl riesig und sagt nichts mehr aus
    reference = expected.where(expected.abs() >= min_reference_power_w)
    return (measured - reference) / reference * 100.0


def _reference_window(end: int, *, rolling_days: int) -> range:
    # Positionen im Tagesindex, end ist der letzte Tag vor dem Beobachtungsfenster
    return range(max(0, end - rolling_days + 1), end + 1)


def _weekday_expected(
    reference: pd.Series, *, min_samples: int, robust: bool
) -> pd.Series:
    values = reference.dropna()
    profile = values.groupby(pd.DatetimeIndex(values.index).dayofweek).agg(
        ["median" if robust else "mean", "count"]
    )
    profile.columns = ["center", "count"]
    profile.loc[profile["count"] < min_samples, "center"] = np.nan

    return pd.Series(
        profile["center"]
        .reindex(pd.DatetimeIndex(reference.index).dayofweek)
        .to_numpy(),
        index=reference.index,
    )


def _weekly_reference(
    weekly_mean: pd.Series,
    *,
    analyzed_position: int,
    weekly_window_days: int,
    rolling_days: int,
) -> pd.Series:
    # nur Wochenmittel, die ganz im Referenzfenster liegen, es endet direkt vor der beobachteten Woche
    window = _reference_window(
        analyzed_position - weekly_window_days, rolling_days=rolling_days
    )
    return _only_positions(
        weekly_mean, range(window.start + weekly_window_days - 1, window.stop)
    )


def _only_positions(values: pd.Series, positions: range) -> pd.Series:
    inside = pd.Series(np.nan, index=values.index)
    if len(positions) > 0:
        inside.iloc[positions.start : positions.stop] = values.iloc[
            positions.start : positions.stop
        ]
    return inside


def _center(values: pd.Series, *, robust: bool) -> float:
    return float(values.median() if robust else values.mean())
