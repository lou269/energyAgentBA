import math
from collections.abc import Mapping
from typing import Literal, TypedDict

import pandas as pd

from src.common.forecast_summary import mean_and_peak, mean_interval_width
from src.common.timestamps import parse_utc_timestamp_field
from src.common.validation import require_non_empty_string
from src.context.calendar_schema import CALENDAR_CONTEXT_FIELDS, CalendarEvent, validate_calendar_context
from src.pipeline.schema_validation import is_real_number, validate_fields


SCHEMA_VERSION = "1.7"

FLOAT_COMPARISON_REL_TOL = 1e-9
FLOAT_COMPARISON_ABS_TOL = 1e-9

ScaleName = Literal["daily", "weekday", "weekly", "long_term"]
TrendName = Literal["stable", "increasing", "decreasing"]
AnomalyLevel = Literal["normal", "unusual", "strong_anomaly"]
AnomalyDirection = Literal["high", "low"]

TREND_NAMES: tuple[TrendName, ...] = ("stable", "increasing", "decreasing")

ANOMALY_LEVELS: tuple[AnomalyLevel, ...] = ("normal", "unusual", "strong_anomaly")

ANOMALY_DIRECTIONS: tuple[AnomalyDirection, ...] = ("high", "low")

SCALE_NAMES: tuple[ScaleName, ...] = ("daily", "weekday", "weekly", "long_term")

OBSERVATION_FIELDS = frozenset(
    {"observation_start", "observation_end", "current_power_w", "value_implausible"}
)

ANALYSIS_FIELDS = frozenset(
    {
        "daily_std",
        "daily_std_expected",
        "today_mean_expected_w",
        "weekday_expected_w",
        "weekly_mean_w",
        "weekly_mean_expected_w",
        "long_term_window_mean_w",
        "long_term_expected_w",
        "trend_slope_w_per_hour",
        "trend_change",
        "trend",
        "weekday_deviation",
    }
)

ANOMALY_FIELDS = frozenset(
    {
        "score",
        "level",
        "direction",
        "dominant_scale",
        "peak_timestamp",
        "scale_scores",
        "scale_anomaly_streak_days",
        "sustained_scales",
        "sustained_drift",
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
    value_implausible: bool


class AnalysisState(TypedDict):
    daily_std: float | None
    daily_std_expected: float | None
    today_mean_expected_w: float | None
    weekday_expected_w: float | None
    weekly_mean_w: float | None
    weekly_mean_expected_w: float | None
    long_term_window_mean_w: float | None
    long_term_expected_w: float | None
    trend_slope_w_per_hour: float | None
    trend_change: float | None
    trend: TrendName | None
    weekday_deviation: float | None


class ScaleScores(TypedDict):
    daily: float | None
    weekday: float | None
    weekly: float | None
    long_term: float | None


class ScaleAnomalyStreakDays(TypedDict):
    daily: float | None
    weekday: float | None
    weekly: float | None
    long_term: float | None


class AnomalyState(TypedDict):
    score: float | None
    level: AnomalyLevel | None
    direction: AnomalyDirection | None
    dominant_scale: ScaleName | None
    peak_timestamp: str | None
    scale_scores: ScaleScores
    scale_anomaly_streak_days: ScaleAnomalyStreakDays
    sustained_scales: list[ScaleName]
    sustained_drift: bool
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

    decision_time = parse_utc_timestamp_field(state["decision_time"], "decision_time")

    observation = _mapping(state["observation"], "observation")
    validate_fields(observation, OBSERVATION_FIELDS, "observation")

    observation_start = parse_utc_timestamp_field(observation["observation_start"], "observation.observation_start")
    observation_end = parse_utc_timestamp_field(observation["observation_end"], "observation.observation_end")

    if observation_end != decision_time:
        raise ValueError("observation_end must equal decision_time.")

    if observation_start >= observation_end:
        raise ValueError("observation_start must be before observation_end.")

    _number(observation["current_power_w"], "observation.current_power_w", nullable=True)

    if not isinstance(observation["value_implausible"], bool):
        raise TypeError("observation.value_implausible must be a boolean.")

    analysis = _mapping(state["analysis"], "analysis")
    validate_fields(analysis, ANALYSIS_FIELDS, "analysis")

    for field in (
        "daily_std",
        "daily_std_expected",
        "today_mean_expected_w",
        "weekday_expected_w",
        "weekly_mean_w",
        "weekly_mean_expected_w",
        "long_term_window_mean_w",
        "long_term_expected_w",
        "trend_slope_w_per_hour",
        "trend_change",
        "weekday_deviation",
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

    scale_streak_days = _mapping(anomaly["scale_anomaly_streak_days"], "anomaly.scale_anomaly_streak_days")
    validate_fields(scale_streak_days, frozenset(SCALE_NAMES), "anomaly.scale_anomaly_streak_days")

    for scale in SCALE_NAMES:
        streak_days = _number(scale_streak_days[scale], f"anomaly.scale_anomaly_streak_days.{scale}", nullable=True)
        if (streak_days is not None) != (scale in validated_scale_scores):
            raise ValueError(f"anomaly.scale_anomaly_streak_days.{scale} must be null exactly when anomaly.scale_scores.{scale} is null.")

        if streak_days is not None and streak_days < 0:
            raise ValueError(f"anomaly.scale_anomaly_streak_days.{scale} must not be negative.")

    available_scales = anomaly["available_scales"]

    if not isinstance(available_scales, list):
        raise TypeError("anomaly.available_scales must be a list.")

    expected_scales = list(validated_scale_scores)

    if available_scales != expected_scales:
        raise ValueError("anomaly.available_scales must match available scale_scores.")

    if score is None:
        if any(anomaly[field] is not None for field in ("level", "direction", "dominant_scale", "peak_timestamp")):
            raise ValueError("Aggregate anomaly fields must be null when anomaly.score is null.")
    else:
        if anomaly["level"] is None or anomaly["peak_timestamp"] is None:
            raise ValueError("anomaly.level and anomaly.peak_timestamp are required when anomaly.score is set.")

        peak_timestamp = parse_utc_timestamp_field(anomaly["peak_timestamp"], "anomaly.peak_timestamp")

        if peak_timestamp > decision_time - pd.Timedelta(hours=1):
            raise ValueError("anomaly.peak_timestamp must not be after the analyzed hour.")

        if anomaly["dominant_scale"] not in available_scales:
            raise ValueError("anomaly.dominant_scale must be an available scale.")

    forecast = _mapping(state["forecast"], "forecast")
    validate_fields(forecast, FORECAST_FIELDS, "forecast")

    for field in ("run_id", "model_id", "config_version"):
        require_non_empty_string(forecast[field], f"forecast.{field}")

    forecast_origin = parse_utc_timestamp_field(forecast["origin"], "forecast.origin")

    if forecast_origin != decision_time:
        raise ValueError("forecast.origin must equal decision_time.")

    points = forecast["points"]

    if not isinstance(points, list):
        raise TypeError("forecast.points must be a list.")

    # keine feste 24, am Tag der Zeitumstellung hat die Prognose eine Stunde mehr oder weniger
    if (
        isinstance(forecast["horizon_hours"], bool)
        or not isinstance(forecast["horizon_hours"], int)
        or forecast["horizon_hours"] != len(points)
    ):
        raise ValueError("forecast.horizon_hours must equal the number of forecast.points.")

    interval_states: list[bool] = []
    point_timestamps: list[pd.Timestamp] = []
    predictions: list[float] = []
    interval_widths: list[float] = []

    for index, point_value in enumerate(points):
        point = _mapping(point_value, f"forecast.points[{index}]")
        validate_fields(point, FORECAST_POINT_FIELDS, f"forecast.points[{index}]")

        timestamp = parse_utc_timestamp_field(point["timestamp"], f"forecast.points[{index}].timestamp")

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

    expected_mean_w, expected_peak_w = mean_and_peak(predictions)

    if not _float_matches(float(mean_w), expected_mean_w):
        raise ValueError("forecast.summary.mean_w must match forecast points.")

    if not _float_matches(float(peak_w), expected_peak_w):
        raise ValueError("forecast.summary.peak_w must match forecast points.")

    peak_timestamp = parse_utc_timestamp_field(summary["peak_timestamp"], "forecast.summary.peak_timestamp")

    expected_peak_timestamps = {
        timestamp
        for timestamp, prediction in zip(point_timestamps, predictions)
        if prediction == expected_peak_w
    }

    if peak_timestamp not in expected_peak_timestamps:
        raise ValueError("forecast.summary.peak_timestamp must reference a peak forecast point.")

    mean_interval_width_w = _number(summary["mean_interval_width_w"], "forecast.summary.mean_interval_width_w", nullable=True)

    if interval_states[0] != (mean_interval_width_w is not None):
        raise ValueError("mean_interval_width_w must be present exactly when prediction intervals are available.")

    if mean_interval_width_w is not None:
        expected_interval_width = mean_interval_width(interval_widths)
        assert expected_interval_width is not None

        if not _float_matches(float(mean_interval_width_w), expected_interval_width):
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