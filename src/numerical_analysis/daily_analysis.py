from typing import cast

import numpy as np
import pandas as pd

from src.common.timestamps import local_day, local_day_index
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.anomaly_detection import (
    build_anomaly_detection,
    build_level_shift_streaks,
)
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis


# beobachtet, erwartet, Werte der Referenztage. long_term hat keinen Z-Score, nur Prozent
DAILY_ANOMALY_SCALES = {
    "daily": ("daily_std", "daily_std_expected", "daily_reference_value"),
    "weekday": ("today_mean", "weekday_expected", "weekday_reference_value"),
    "weekly": ("weekly_mean", "weekly_mean_expected", "weekly_reference_value"),
}

DAILY_DIRECTION_OVERRIDE_COLUMNS = {
    "daily": ("today_mean", "today_mean_expected"),
}

# der Wert, den die Streak je Niveau-Skala zählt
LEVEL_SHIFT_VALUE_COLUMNS = {
    "weekday": "weekday_score",
    "weekly": "weekly_score",
    "long_term": "long_term_deviation_pct",
}


def level_shift_thresholds(config: NumericalAnalysisConfig) -> dict[str, float]:
    return {
        "weekday": config.weekday_streak_threshold,
        "weekly": config.weekly_streak_threshold,
        "long_term": config.long_term_streak_threshold_pct,
    }


def compute_analysis_row(
    history: pd.Series,
    *,
    target_timestamp: pd.Timestamp,
    config: NumericalAnalysisConfig,
    local_timezone: str,
    raw_value_implausible: pd.Series | None = None,
) -> pd.Series | None:
    # ohne einen Tag vor dem eingeordneten gibt es keine Referenz, z.B. direkt nach einem Reset
    if local_day_index(history.index, local_timezone).nunique() < 2:
        return None

    target_day = local_day(target_timestamp, local_timezone)

    analysis = build_multi_scale_analysis(
        history,
        analyzed_day=target_day,
        reference_window_rolling_days=config.reference_window_rolling_days,
        short_term_window=config.trend_window_days,
        sample_period_hours=config.sample_period_hours_daily,
        long_term_window=config.long_term_window_days,
        long_term_reference_days=config.long_term_reference_days,
        weekly_window_days=config.weekly_window_days,
        min_weekday_reference_samples=config.min_weekday_reference_samples,
        min_longterm_reference_samples=config.min_longterm_reference_samples,
        trend_threshold=config.trend_threshold,
        min_reference_power_w=config.min_reference_power_w,
        rolling_window_min_coverage=config.rolling_window_min_coverage,
        robust_scales=config.single_day_scales,
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
        },
        min_residual_std_w=config.min_residual_std_w,
        unusual_thresholds={
            scale: config.unusual_threshold for scale in config.single_day_scales
        },
        single_day_scales=config.single_day_scales,
        # Einzeltag-Skalen sind zugleich die robusten (Median/MAD)
        robust_scales=config.single_day_scales,
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


def add_level_shift_streaks(
    analysis_row: pd.Series,
    score_history: pd.DataFrame,
    *,
    config: NumericalAnalysisConfig,
) -> tuple[pd.Series, pd.DataFrame]:
    # die Streak zählt die Werte, die jede Skala an ihrem eigenen Entscheidungstag hatte, nicht neu gerechnete
    today = pd.DataFrame(
        {
            scale: [analysis_row[LEVEL_SHIFT_VALUE_COLUMNS[scale]]]
            for scale in config.level_shift_scales
        },
        index=[analysis_row["timestamp"]],
    )
    score_history = today if score_history.empty else pd.concat([score_history, today])

    streaks = build_level_shift_streaks(
        score_history,
        streak_thresholds=level_shift_thresholds(config),
        sustained_anomaly_streak_days=config.sustained_anomaly_streak_days,
        min_sustained_scales=config.min_sustained_scales,
        streak_tolerance_window_days=config.streak_tolerance_window_days,
        rolling_window_min_coverage=config.rolling_window_min_coverage,
    ).iloc[-1]

    row = pd.concat([analysis_row, streaks])
    # daily zählt nicht für new_pattern, der State-Builder erwartet die Felder aber, sie bleiben leer
    for scale in DAILY_ANOMALY_SCALES:
        if scale not in config.level_shift_scales:
            row[f"{scale}_anomaly_streak_days"] = np.nan
            row[f"{scale}_sustained"] = False

    return row, score_history
