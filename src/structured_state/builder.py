import math
from numbers import Real
from typing import TypeVar, cast

import numpy as np
import pandas as pd

from src.common.timestamps import parse_utc_timestamp
from src.context.calendar_schema import CalendarContext
from src.pipeline.schema_validation import is_real_number
from src.structured_state.structured_state_schema import (
    ANOMALY_DIRECTIONS,
    ANOMALY_LEVELS,
    TREND_NAMES,
    FORECAST_HORIZON_HOURS,
    SCALE_NAMES,
    SCHEMA_VERSION,
    ContextState,
    ForecastPoint,
    ForecastState,
    ScaleAnomalyStreakDays,
    ScaleName,
    ScaleScores,
    StructuredState,
)


ANALYSIS_FIELDS = frozenset(
    {
        "timestamp",
        "split",
        "today_mean",
        "daily_std",
        "daily_std_expected",
        "today_mean_expected",
        "weekday_expected",
        "weekly_mean",
        "weekly_mean_expected",
        "long_term_window_mean",
        "long_term_expected",
        "trend_slope_w_per_hour",
        "trend_change",
        "trend",
        "daily_score",
        "weekday_score",
        "weekly_score",
        "long_term_score",
        "daily_anomaly_streak_days",
        "weekday_anomaly_streak_days",
        "weekly_anomaly_streak_days",
        "long_term_anomaly_streak_days",
        "anomaly_score",
        "dominant_scale",
        "anomaly_direction",
        "anomaly_level",
        "anomaly_peak_timestamp",
        "value_implausible",
    }
)

FORECAST_COLUMNS = frozenset(
    {
        "run_id",
        "split",
        "model_id",
        "config_version",
        "forecast_origin",
        "target_timestamp",
        "y_pred",
        "y_lower",
        "y_upper",
    }
)

TextType = TypeVar("TextType", bound=str)


def build_structured_state(
    *,
    decision_time: str | pd.Timestamp,
    analysis_row: pd.Series,
    forecast_rows: pd.DataFrame,
    calendar_context: CalendarContext,
) -> StructuredState:
    decision_time = parse_utc_timestamp(decision_time, "decision_time")

    missing = ANALYSIS_FIELDS.difference(analysis_row.index)
    if missing:
        raise ValueError("Analysis row is missing required fields: " + ", ".join(sorted(missing)))

    missing = FORECAST_COLUMNS.difference(forecast_rows.columns)
    if missing:
        raise ValueError("Forecast rows are missing required columns: " + ", ".join(sorted(missing)))

    analysis_timestamp = parse_utc_timestamp(analysis_row["timestamp"], "analysis.timestamp")

    if analysis_timestamp >= decision_time:
        raise ValueError("Analysis timestamp must be before decision_time.")

    context_decision_time = parse_utc_timestamp(calendar_context["decision_time"], "calendar_context.decision_time")

    if context_decision_time != decision_time:
        raise ValueError("Calendar context decision_time must match decision_time.")

    scale_scores: ScaleScores = {
        "daily": _nullable_float(analysis_row["daily_score"], "analysis.daily_score"),
        "weekday": _nullable_float(analysis_row["weekday_score"], "analysis.weekday_score"),
        "weekly": _nullable_float(analysis_row["weekly_score"], "analysis.weekly_score"),
        "long_term": _nullable_float(analysis_row["long_term_score"], "analysis.long_term_score"),
    }

    scale_streak_days: ScaleAnomalyStreakDays = {
        "daily": _nullable_float(analysis_row["daily_anomaly_streak_days"], "analysis.daily_anomaly_streak_days"),
        "weekday": _nullable_float(analysis_row["weekday_anomaly_streak_days"], "analysis.weekday_anomaly_streak_days"),
        "weekly": _nullable_float(analysis_row["weekly_anomaly_streak_days"], "analysis.weekly_anomaly_streak_days"),
        "long_term": _nullable_float(analysis_row["long_term_anomaly_streak_days"], "analysis.long_term_anomaly_streak_days"),
    }

    available_scales: list[ScaleName] = [scale for scale in SCALE_NAMES if scale_scores[scale] is not None]

    forecast_state = _build_forecast_state(
        forecast_rows=forecast_rows,
        decision_time=decision_time,
        analysis_split=analysis_row["split"],
    )

    context: ContextState = {
        "source_available": calendar_context["source_available"],
        "source": calendar_context["source"],
        "retrieved_at": calendar_context["retrieved_at"],
        "window_start": calendar_context["window_start"],
        "window_end": calendar_context["window_end"],
        "events": list(calendar_context["events"]),
    }

    state: StructuredState = {
        "schema_version": SCHEMA_VERSION,
        "decision_time": decision_time.isoformat(),
        "observation": {
            "observation_start": analysis_timestamp.isoformat(),
            "observation_end": decision_time.isoformat(),
            "current_power_w": _nullable_float(analysis_row["today_mean"], "analysis.today_mean"),
            "value_implausible": _bool(analysis_row["value_implausible"], "analysis.value_implausible"),
        },
        "analysis": {
            "daily_std": _nullable_float(analysis_row["daily_std"], "analysis.daily_std"),
            "daily_std_expected": _nullable_float(analysis_row["daily_std_expected"], "analysis.daily_std_expected"),
            "today_mean_expected_w": _nullable_float(analysis_row["today_mean_expected"], "analysis.today_mean_expected"),
            "weekday_expected_w": _nullable_float(analysis_row["weekday_expected"], "analysis.weekday_expected"),
            "weekly_mean_w": _nullable_float(analysis_row["weekly_mean"], "analysis.weekly_mean"),
            "weekly_mean_expected_w": _nullable_float(analysis_row["weekly_mean_expected"], "analysis.weekly_mean_expected"),
            "long_term_window_mean_w": _nullable_float(analysis_row["long_term_window_mean"], "analysis.long_term_window_mean"),
            "long_term_expected_w": _nullable_float(analysis_row["long_term_expected"], "analysis.long_term_expected"),
            "trend_slope_w_per_hour": _nullable_float( analysis_row["trend_slope_w_per_hour"], "analysis.trend_slope_w_per_hour"),
            "trend_change": _nullable_float(analysis_row["trend_change"], "analysis.trend_change"),
            "trend": _nullable_text(analysis_row["trend"], "analysis.trend", TREND_NAMES),
        },
        "anomaly": {
            "score": _nullable_float(analysis_row["anomaly_score"], "analysis.anomaly_score"),
            "level": _nullable_text(analysis_row["anomaly_level"], "anomaly.level", ANOMALY_LEVELS),
            "direction": _nullable_text(analysis_row["anomaly_direction"],"anomaly.direction", ANOMALY_DIRECTIONS),
            "dominant_scale": _nullable_text(analysis_row["dominant_scale"], "anomaly.dominant_scale", SCALE_NAMES),
            "peak_timestamp": _nullable_timestamp(analysis_row["anomaly_peak_timestamp"], "analysis.anomaly_peak_timestamp"),
            "scale_scores": scale_scores,
            "scale_anomaly_streak_days": scale_streak_days,
            "available_scales": available_scales,
        },
        "forecast": forecast_state,
        "context": context,
    }

    return state


def _build_forecast_state(
    *, 
    forecast_rows: pd.DataFrame, 
    decision_time: pd.Timestamp, 
    analysis_split: object
) -> ForecastState:
    if forecast_rows.empty:
        raise ValueError("Forecast rows must not be empty.")

    if len(forecast_rows) != FORECAST_HORIZON_HOURS:
        raise ValueError(f"Forecast must contain exactly {FORECAST_HORIZON_HOURS} rows.")

    forecast = forecast_rows.sort_values("target_timestamp").reset_index(drop=True)

    run_id = _single_text(forecast, "run_id")
    model_id = _single_text(forecast, "model_id")
    config_version = str(_single_value(forecast, "config_version"))
    forecast_split = _single_text(forecast, "split")

    if _is_missing(analysis_split) or str(analysis_split) != forecast_split:
        raise ValueError("Analysis and forecast must belong to the same split.")

    forecast_origin = parse_utc_timestamp(_single_value(forecast, "forecast_origin"), "forecast.forecast_origin")

    if forecast_origin != decision_time:
        raise ValueError("Forecast origin must equal decision_time.")

    forecast_points: list[ForecastPoint] = []
    predictions: list[float] = []
    interval_widths: list[float] = []

    for index, row in forecast.iterrows():
        timestamp = parse_utc_timestamp(row["target_timestamp"], f"forecast row {index} target_timestamp")
        prediction = _nullable_float(row["y_pred"], f"forecast row {index} y_pred")

        if prediction is None:
            raise ValueError(f"forecast row {index} y_pred must not be missing.")

        lower = _nullable_float(row["y_lower"], f"forecast row {index} y_lower")
        upper = _nullable_float(row["y_upper"], f"forecast row {index} y_upper")

        if lower is not None and upper is not None:
            interval_widths.append(upper - lower)

        predictions.append(prediction)

        forecast_points.append(
            {
                "timestamp": timestamp.isoformat(),
                "predicted_power_w": prediction,
                "lower_w": lower,
                "upper_w": upper,
            }
        )

    peak_w = max(predictions)
    peak_index = predictions.index(peak_w)

    return {
        "run_id": run_id,
        "model_id": model_id,
        "config_version": config_version,
        "origin": forecast_origin.isoformat(),
        "horizon_hours": FORECAST_HORIZON_HOURS,
        "points": forecast_points,
        "summary": {
            "mean_w": sum(predictions) / len(predictions),
            "peak_w": peak_w,
            "peak_timestamp": forecast_points[peak_index]["timestamp"],
            "mean_interval_width_w": sum(interval_widths) / len(interval_widths) if interval_widths else None
        },
    }


def _single_value(
    frame: pd.DataFrame, 
    column: str
) -> object:
    values = frame[column].drop_duplicates()

    if len(values) != 1:
        raise ValueError(f"Forecast column {column} must contain exactly one value.")

    value = values.iloc[0]
    if _is_missing(value):
        raise ValueError(f"Forecast column {column} must not be missing.")

    return value


def _single_text(
    frame: pd.DataFrame, 
    column: str
) -> str:
    value = _single_value(frame, column)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Forecast column {column} must contain a non-empty string.")

    return value


def _nullable_float(
    value: object, 
    field_name: str
) -> float | None:
    if _is_missing(value):
        return None

    if not is_real_number(value):
        raise TypeError(f"{field_name} must be numeric or null.")

    number = float(value)

    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")

    return number


def _nullable_text(
    value: object, 
    field_name: str, 
    allowed: tuple[TextType, ...]
) -> TextType | None:
    if _is_missing(value):
        return None

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or null.")

    if value not in allowed:
        raise ValueError(f"{field_name} contains an unsupported value.")

    return cast(TextType, value)


def _nullable_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if _is_missing(value):
        return None

    return parse_utc_timestamp(value, field_name).isoformat()


def _bool(
    value: object,
    field_name: str,
) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)

    raise TypeError(f"{field_name} must be a boolean.")


def _is_missing(value: object) -> bool:
    if value is None or value is pd.NA or value is pd.NaT:
        return True

    if isinstance(value, Real):
        return math.isnan(float(value))

    return False