from typing import cast

import pandas as pd

from src.common.timestamps import local_day, local_day_index, shift_local_days
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.anomaly_detection import build_anomaly_detection
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis


DAILY_ANOMALY_SCALES = {
    "daily": ("daily_std", "daily_std_expected"),
    "weekday": ("today_mean", "weekday_expected"),
    "weekly": ("weekly_mean", "weekly_mean_expected"),
    "long_term": ("long_term_window_mean", "long_term_expected"),
}

DAILY_DIRECTION_OVERRIDE_COLUMNS = {
    "daily": ("today_mean", "today_mean_expected"),
}


def compute_reference_window_end(
    history: pd.Series,
    *,
    local_timezone: str,
    max_growth_days: int | None,
    reference_window_days: int,
) -> pd.Timestamp | None:
    history_days = local_day_index(history.index, local_timezone)

    if history_days.nunique() < reference_window_days:
        # kurz nach einem advance_history_start-Reset kann history vorübergehend unter die Mindestgröße fallen
        # -> Analyse für diesen einen Zyklus auslassen statt abzubrechen
        return None

    last_day = history_days.max()
    if max_growth_days is not None:
        last_day = min(
            last_day, history_days.min() + pd.DateOffset(days=max_growth_days - 1)
        )

    return shift_local_days(last_day, -(reference_window_days - 1), local_timezone)


def compute_analysis_row(
    history: pd.Series,
    *,
    target_timestamp: pd.Timestamp,
    config: NumericalAnalysisConfig,
    local_timezone: str,
    raw_value_implausible: pd.Series | None = None,
) -> pd.Series | None:
    reference_window_end = compute_reference_window_end(
        history,
        local_timezone=local_timezone,
        max_growth_days=config.max_reference_window_growth_days,
        reference_window_days=config.reference_window_days,
    )
    if reference_window_end is None:
        return None

    target_day = local_day(target_timestamp, local_timezone)

    analysis = build_multi_scale_analysis(
        history,
        reference_window_end=reference_window_end,
        reference_window_rolling_days=config.reference_window_rolling_days,
        short_term_window=config.trend_window_days,
        sample_period_hours=config.sample_period_hours_daily,
        long_term_window=config.long_term_window_days,
        weekly_window_days=config.weekly_window_days,
        min_weekday_reference_samples=config.min_weekday_reference_samples,
        trend_threshold=config.trend_threshold,
        min_reference_power_w=config.min_reference_power_w,
        rolling_window_min_coverage=config.rolling_window_min_coverage,
        local_timezone=local_timezone,
    )

    anomaly = build_anomaly_detection(
        analysis,
        reference_columns=DAILY_ANOMALY_SCALES,
        direction_override_columns=DAILY_DIRECTION_OVERRIDE_COLUMNS,
        min_reference_samples={
            "daily": config.min_daily_reference_samples,
            "weekday": config.min_weekday_reference_samples,
            "weekly": config.min_weekly_reference_samples,
            "long_term": config.min_longterm_reference_samples,
        },
        min_residual_std_w=config.min_residual_std_w,
        unusual_threshold=config.unusual_threshold,
        strong_anomaly_threshold=config.strong_anomaly_threshold,
        gate_scales=config.gate_scales,
        streak_thresholds={
            "weekly": config.weekly_streak_threshold,
            "long_term": config.long_term_streak_threshold,
        },
        sustained_anomaly_streak_days=config.sustained_anomaly_streak_days,
        min_sustained_scales=config.min_sustained_scales,
        streak_tolerance_window_days=config.streak_tolerance_window_days,
        rolling_window_min_coverage=config.rolling_window_min_coverage,
    )

    row = cast(pd.Series, anomaly.loc[target_day]).copy()
    row["timestamp"] = target_day.tz_convert("UTC")

    day_implausible = False
    if raw_value_implausible is not None:
        day_implausible = bool(
            raw_value_implausible[
                local_day_index(raw_value_implausible.index, local_timezone)
                == target_day
            ].any()
        )
    row["value_implausible"] = bool(pd.isna(row["today_mean"])) or day_implausible

    return row
