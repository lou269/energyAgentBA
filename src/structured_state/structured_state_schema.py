from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Literal, TypedDict

import pandas as pd

from src.context.calendar_schema import CALENDAR_CONTEXT_FIELDS, CalendarEvent, validate_calendar_context
from src.pipeline.schema_validation import is_real_number, validate_fields


SCHEMA_VERSION = "1.0"
FORECAST_HORIZON_HOURS = 24

FLOAT_COMPARISON_REL_TOL = 1e-9
FLOAT_COMPARISON_ABS_TOL = 1e-9

ScaleName = Literal["short_term", "daily", "weekly", "long_term"]
TrendName = Literal["stable", "increasing", "decreasing"]
AnomalyLevel = Literal["normal", "unusual", "strong_anomaly"]
AnomalyDirection = Literal["high", "low"]

TREND_NAMES: tuple[TrendName, ...] = ("stable", "increasing", "decreasing")

ANOMALY_LEVELS: tuple[AnomalyLevel, ...] = ("normal", "unusual", "strong_anomaly")

ANOMALY_DIRECTIONS: tuple[AnomalyDirection, ...] = ("high", "low")

SCALE_NAMES: tuple[ScaleName, ...] = ("short_term", "daily", "weekly", "long_term")

OBSERVATION_FIELDS = frozenset(
    {"observation_start", "observation_end", "current_power_w"}
)

ANALYSIS_FIELDS = frozenset(
    {
        "short_term_mean_w",
        "daily_expected_w",
        "weekly_expected_w",
        "long_term_mean_w",
        "trend_slope_w_per_hour",
        "trend_change",
        "trend",
    }
)

ANOMALY_FIELDS = frozenset(
    {
        "score",
        "level",
        "direction",
        "dominant_scale",
        "scale_scores",
        "scale_streak_hours",
        "available_scales",
    }
)

FORECAST_FIELDS = frozenset(
    {
        "run_id",
        "model_id",
        "config_version",
        "origin",
        "horizon_hours",
        "points",
        "summary",
    }
)

FORECAST_POINT_FIELDS = frozenset(
    {"timestamp", "predicted_power_w", "lower_w", "upper_w"}
)

FORECAST_SUMMARY_FIELDS = frozenset(
    {"mean_w", "peak_w", "peak_timestamp", "mean_interval_width_w"}
)

CONTEXT_FIELDS = CALENDAR_CONTEXT_FIELDS - {"decision_time"}

STRUCTURED_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "decision_time",
        "observation",
        "analysis",
        "anomaly",
        "forecast",
        "context",
    }
)


class ObservationState(TypedDict):
    observation_start: str
    observation_end: str
    current_power_w: float | None


class AnalysisState(TypedDict):
    short_term_mean_w: float | None
    daily_expected_w: float | None
    weekly_expected_w: float | None
    long_term_mean_w: float | None
    trend_slope_w_per_hour: float | None
    trend_change: float | None
    trend: TrendName | None


class ScaleScores(TypedDict):
    short_term: float | None
    daily: float | None
    weekly: float | None
    long_term: float | None


class ScaleStreaks(TypedDict):
    short_term: float | None
    daily: float | None
    weekly: float | None
    long_term: float | None


class AnomalyState(TypedDict):
    score: float | None
    level: AnomalyLevel | None
    direction: AnomalyDirection | None
    dominant_scale: ScaleName | None
    scale_scores: ScaleScores
    scale_streak_hours: ScaleStreaks
    available_scales: list[ScaleName]


class ForecastPoint(TypedDict):
    timestamp: str
    predicted_power_w: float
    lower_w: float | None
    upper_w: float | None


class ForecastSummary(TypedDict):
    mean_w: float
    peak_w: float
    peak_timestamp: str
    mean_interval_width_w: float | None


class ForecastState(TypedDict):
    run_id: str
    model_id: str
    config_version: str
    origin: str
    horizon_hours: int
    points: list[ForecastPoint]
    summary: ForecastSummary


class ContextState(TypedDict):
    source_available: bool
    source: str
    retrieved_at: str
    window_start: str
    window_end: str
    events: list[CalendarEvent]


class StructuredState(TypedDict):
    schema_version: str
    decision_time: str
    observation: ObservationState
    analysis: AnalysisState
    anomaly: AnomalyState
    forecast: ForecastState
    context: ContextState


def validate_structured_state(
    state: Mapping[str, object]
)-> None:
    validate_fields(state, STRUCTURED_STATE_FIELDS, "Structured State")

    if state["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}.")

    decision_time = _timestamp(state["decision_time"], "decision_time")

    observation = _mapping(state["observation"], "observation")
    validate_fields(observation, OBSERVATION_FIELDS, "observation")

    observation_start = _timestamp(observation["observation_start"], "observation.observation_start")
    observation_end = _timestamp(observation["observation_end"], "observation.observation_end")

    if observation_start != decision_time - pd.Timedelta(hours=1):
        raise ValueError("observation_start must be exactly one hour before decision_time.")

    if observation_end != decision_time:
        raise ValueError("observation_end must equal decision_time.")

    _number(observation["current_power_w"], "observation.current_power_w", nullable=True)

    analysis = _mapping(state["analysis"], "analysis")
    validate_fields(analysis, ANALYSIS_FIELDS, "analysis")

    for field in (
        "short_term_mean_w",
        "daily_expected_w",
        "weekly_expected_w",
        "long_term_mean_w",
        "trend_slope_w_per_hour",
        "trend_change",
    ):
        _number(analysis[field], f"analysis.{field}", nullable=True)

    if analysis["trend"] is not None and analysis["trend"] not in TREND_NAMES:
        raise ValueError("analysis.trend contains an unsupported value.")

    anomaly = _mapping(state["anomaly"], "anomaly")
    validate_fields(anomaly, ANOMALY_FIELDS, "anomaly")

    score = _number(anomaly["score"], "anomaly.score", nullable=True)

    if score is not None and score < 0:
        raise ValueError("anomaly.score must not be negative.")

    if anomaly["level"] is not None and anomaly["level"] not in ANOMALY_LEVELS:
        raise ValueError("anomaly.level contains an unsupported value.")

    if (
        anomaly["direction"] is not None
        and anomaly["direction"] not in ANOMALY_DIRECTIONS
    ):
        raise ValueError("anomaly.direction contains an unsupported value.")

    if (
        anomaly["dominant_scale"] is not None
        and anomaly["dominant_scale"] not in SCALE_NAMES
    ):
        raise ValueError("anomaly.dominant_scale contains an unsupported value.")

    scale_scores = _mapping(anomaly["scale_scores"], "anomaly.scale_scores")
    validate_fields(scale_scores, frozenset(SCALE_NAMES), "anomaly.scale_scores")

    validated_scale_scores: dict[ScaleName, float] = {}

    for scale in SCALE_NAMES:
        scale_score = _number(scale_scores[scale], f"anomaly.scale_scores.{scale}", nullable=True)
        if scale_score is not None:
            validated_scale_scores[scale] = float(scale_score)

    scale_streak_hours = _mapping(anomaly["scale_streak_hours"], "anomaly.scale_streak_hours")
    validate_fields(scale_streak_hours, frozenset(SCALE_NAMES), "anomaly.scale_streak_hours")

    for scale in SCALE_NAMES:
        streak_hours = _number(scale_streak_hours[scale], f"anomaly.scale_streak_hours.{scale}", nullable=True)
        if (streak_hours is not None) != (scale in validated_scale_scores):
            raise ValueError(f"anomaly.scale_streak_hours.{scale} must be null exactly when anomaly.scale_scores.{scale} is null.")

        if streak_hours is not None and streak_hours < 0:
            raise ValueError(f"anomaly.scale_streak_hours.{scale} must not be negative.")

    available_scales = anomaly["available_scales"]

    if not isinstance(available_scales, list):
        raise TypeError("anomaly.available_scales must be a list.")

    expected_scales = list(validated_scale_scores)

    if available_scales != expected_scales:
        raise ValueError("anomaly.available_scales must match available scale_scores.")

    if not available_scales:
        if any(
            anomaly[field] is not None
            for field in ("score", "level", "direction", "dominant_scale")
        ):
            raise ValueError("Aggregate anomaly fields must be null when no scale scores are available.")
    else:
        if anomaly["score"] is None or anomaly["level"] is None:
            raise ValueError("anomaly.score and anomaly.level are required when scale scores are available.")

        if anomaly["dominant_scale"] not in available_scales:
            raise ValueError("anomaly.dominant_scale must be an available scale.")

        expected_score = max(abs(scale_score) for scale_score in validated_scale_scores.values())

        if score is None or not _float_matches(float(score), expected_score):
            raise ValueError("anomaly.score must match the largest absolute available scale score.")

        dominant_scales = [
            scale
            for scale, scale_score in validated_scale_scores.items()
            if _float_matches(abs(scale_score), expected_score)
        ]

        if anomaly["dominant_scale"] not in dominant_scales:
            raise ValueError("anomaly.dominant_scale must reference a scale with the largest absolute scale score.")

        dominant_score = next(
            scale_score
            for scale, scale_score in validated_scale_scores.items()
            if scale == anomaly["dominant_scale"]
        )

        if dominant_score > 0 and anomaly["direction"] != "high":
            raise ValueError("anomaly.direction must be 'high' for a positive dominant scale score.")

        if dominant_score < 0 and anomaly["direction"] != "low":
            raise ValueError("anomaly.direction must be 'low' for a negative dominant scale score.")

        if dominant_score == 0 and anomaly["direction"] is not None:
            raise ValueError("anomaly.direction must be null when the dominant scale score is zero.")

    forecast = _mapping(state["forecast"], "forecast")
    validate_fields(forecast, FORECAST_FIELDS, "forecast")

    for field in ("run_id", "model_id", "config_version"):
        _non_empty_string(forecast[field], f"forecast.{field}")

    forecast_origin = _timestamp(forecast["origin"], "forecast.origin")

    if forecast_origin != decision_time:
        raise ValueError("forecast.origin must equal decision_time.")

    if (
        isinstance(forecast["horizon_hours"], bool)
        or not isinstance(forecast["horizon_hours"], int)
        or forecast["horizon_hours"] != FORECAST_HORIZON_HOURS
    ):
        raise ValueError(f"forecast.horizon_hours must be {FORECAST_HORIZON_HOURS}.")

    points = forecast["points"]

    if not isinstance(points, list):
        raise TypeError("forecast.points must be a list.")

    if len(points) != FORECAST_HORIZON_HOURS:
        raise ValueError(f"forecast.points must contain exactly {FORECAST_HORIZON_HOURS} points.")

    interval_states: list[bool] = []
    point_timestamps: list[pd.Timestamp] = []
    predictions: list[float] = []
    interval_widths: list[float] = []

    for index, point_value in enumerate(points):
        point = _mapping(point_value, f"forecast.points[{index}]")
        validate_fields(point, FORECAST_POINT_FIELDS, f"forecast.points[{index}]")

        timestamp = _timestamp(point["timestamp"], f"forecast.points[{index}].timestamp")

        if timestamp != forecast_origin + pd.Timedelta(hours=index):
            raise ValueError("Forecast point timestamps must be consecutive hourly timestamps starting at forecast.origin.")

        prediction = _number(point["predicted_power_w"], f"forecast.points[{index}].predicted_power_w")
        assert prediction is not None
        predictions.append(float(prediction))

        lower = _number(point["lower_w"], f"forecast.points[{index}].lower_w", nullable=True)
        upper = _number(point["upper_w"], f"forecast.points[{index}].upper_w", nullable=True)

        if (lower is None) != (upper is None):
            raise ValueError("Forecast lower_w and upper_w must be provided together.")

        if lower is not None and upper is not None and lower > upper:
            raise ValueError("Forecast lower_w must not exceed upper_w.")

        if lower is not None and upper is not None and not lower <= prediction <= upper:
            raise ValueError("Forecast prediction must lie within its prediction interval.")

        interval_states.append(lower is not None)
        point_timestamps.append(timestamp)

        if lower is not None and upper is not None:
            interval_widths.append(float(upper - lower))

    if len(set(interval_states)) > 1:
        raise ValueError("Prediction intervals must be available for all forecast points or for none.")

    summary = _mapping(forecast["summary"], "forecast.summary")
    validate_fields(summary, FORECAST_SUMMARY_FIELDS, "forecast.summary")

    mean_w = _number(summary["mean_w"], "forecast.summary.mean_w")
    peak_w = _number(summary["peak_w"], "forecast.summary.peak_w")
    assert mean_w is not None
    assert peak_w is not None

    expected_mean_w = sum(predictions) / len(predictions)
    expected_peak_w = max(predictions)

    if not _float_matches(float(mean_w), expected_mean_w):
        raise ValueError("forecast.summary.mean_w must match forecast points.")

    if not _float_matches(float(peak_w), expected_peak_w):
        raise ValueError("forecast.summary.peak_w must match forecast points.")

    peak_timestamp = _timestamp(summary["peak_timestamp"], "forecast.summary.peak_timestamp")

    expected_peak_timestamps = {
        timestamp
        for timestamp, prediction in zip(point_timestamps, predictions)
        if prediction == expected_peak_w
    }

    if peak_timestamp not in expected_peak_timestamps:
        raise ValueError("forecast.summary.peak_timestamp must reference a peak forecast point.")

    mean_interval_width = _number(summary["mean_interval_width_w"], "forecast.summary.mean_interval_width_w", nullable=True)

    if interval_states[0] != (mean_interval_width is not None):
        raise ValueError("mean_interval_width_w must be present exactly when prediction intervals are available.")

    if mean_interval_width is not None:
        expected_interval_width = sum(interval_widths) / len(interval_widths)

        if not _float_matches(float(mean_interval_width), expected_interval_width):
            raise ValueError("forecast.summary.mean_interval_width_w must match forecast points.")

    context = _mapping(state["context"], "context")
    validate_fields(context, CONTEXT_FIELDS, "context")

    calendar_context = dict(context)
    calendar_context["decision_time"] = state["decision_time"]
    validate_calendar_context(calendar_context)


def _mapping(
    value: object, 
    field_name: str
 ) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")

    return value


def _non_empty_string(
    value: object, 
    field_name: str
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value


def _float_matches(
    actual: float, 
    expected: float
) -> bool:
    return math.isclose(
        actual,
        expected,
        rel_tol=FLOAT_COMPARISON_REL_TOL,
        abs_tol=FLOAT_COMPARISON_ABS_TOL,
    )


def _number(
    value: object, 
    field_name: str, 
    *, 
    nullable: bool = False
) -> float | None:
    
    if value is None:
        if nullable:
            return None

        raise ValueError(f"{field_name} must not be null.")

    if not is_real_number(value):
        raise TypeError(f"{field_name} must be numeric.")

    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite.")

    return float(value)


def _timestamp(
    value: object, 
    field_name: str
) -> pd.Timestamp:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string timestamp.")

    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{field_name} must be a valid timestamp.") from error

    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must contain timezone information.")

    timestamp = timestamp.tz_convert("UTC")

    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    if normalized_value != timestamp.isoformat():
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp.")

    return timestamp