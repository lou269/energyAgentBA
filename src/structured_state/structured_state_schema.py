import math
from collections.abc import Mapping
from typing import Literal, TypedDict

from src.common.timestamps import parse_utc_timestamp_field
from src.context.calendar_schema import (
    CALENDAR_CONTEXT_FIELDS,
    CalendarEvent,
    validate_calendar_context,
)
from src.pipeline.schema_validation import is_real_number, validate_fields


SCHEMA_VERSION = "1.8"

ScaleName = Literal["daily", "weekday", "weekly", "long_term"]
AnomalyLevel = Literal["normal", "unusual", "strong_anomaly"]
AnomalyDirection = Literal["high", "low"]

ANOMALY_LEVELS: tuple[AnomalyLevel, ...] = ("normal", "unusual", "strong_anomaly")

ANOMALY_DIRECTIONS: tuple[AnomalyDirection, ...] = ("high", "low")

SCALE_NAMES: tuple[ScaleName, ...] = ("daily", "weekday", "weekly", "long_term")

# daily misst die Streuung im Tag, dafür gibt es keine sinnvolle Prozentabweichung der Menge
DeviationScaleName = Literal["weekday", "weekly", "long_term"]
DEVIATION_SCALE_NAMES: tuple[DeviationScaleName, ...] = (
    "weekday",
    "weekly",
    "long_term",
)

OBSERVATION_FIELDS = frozenset(
    {"observation_start", "observation_end", "value_implausible"}
)

ANOMALY_FIELDS = frozenset(
    {
        "level",
        "direction",
        "scale_scores",
        "scale_anomaly_streak_days",
        "scale_deviation_pct",
        "sustained_scales",
        "sustained_drift",
        "available_scales",
    }
)

CONTEXT_FIELDS = CALENDAR_CONTEXT_FIELDS - {"decision_time"}

STRUCTURED_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "decision_time",
        "observation",
        "anomaly",
        "context",
    }
)


class ObservationState(TypedDict):
    observation_start: str
    observation_end: str
    value_implausible: bool


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


class ScaleDeviationPct(TypedDict):
    weekday: float | None
    weekly: float | None
    long_term: float | None


class AnomalyState(TypedDict):
    level: AnomalyLevel | None
    direction: AnomalyDirection | None
    scale_scores: ScaleScores
    scale_anomaly_streak_days: ScaleAnomalyStreakDays
    scale_deviation_pct: ScaleDeviationPct
    sustained_scales: list[ScaleName]
    sustained_drift: bool
    available_scales: list[ScaleName]


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
    anomaly: AnomalyState
    context: ContextState


def validate_structured_state(state: Mapping[str, object]) -> None:
    validate_fields(state, STRUCTURED_STATE_FIELDS, "Structured State")

    if state["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}.")

    decision_time = parse_utc_timestamp_field(state["decision_time"], "decision_time")

    observation = _mapping(state["observation"], "observation")
    validate_fields(observation, OBSERVATION_FIELDS, "observation")

    observation_start = parse_utc_timestamp_field(
        observation["observation_start"], "observation.observation_start"
    )
    observation_end = parse_utc_timestamp_field(
        observation["observation_end"], "observation.observation_end"
    )

    if observation_end != decision_time:
        raise ValueError("observation_end must equal decision_time.")

    if observation_start >= observation_end:
        raise ValueError("observation_start must be before observation_end.")

    if not isinstance(observation["value_implausible"], bool):
        raise TypeError("observation.value_implausible must be a boolean.")

    anomaly = _mapping(state["anomaly"], "anomaly")
    validate_fields(anomaly, ANOMALY_FIELDS, "anomaly")

    if anomaly["level"] is not None and anomaly["level"] not in ANOMALY_LEVELS:
        raise ValueError("anomaly.level contains an unsupported value.")

    if (
        anomaly["direction"] is not None
        and anomaly["direction"] not in ANOMALY_DIRECTIONS
    ):
        raise ValueError("anomaly.direction contains an unsupported value.")

    scale_scores = _mapping(anomaly["scale_scores"], "anomaly.scale_scores")
    validate_fields(scale_scores, frozenset(SCALE_NAMES), "anomaly.scale_scores")

    validated_scale_scores: dict[ScaleName, float] = {}

    for scale in SCALE_NAMES:
        scale_score = _number(
            scale_scores[scale], f"anomaly.scale_scores.{scale}", nullable=True
        )
        if scale_score is not None:
            validated_scale_scores[scale] = float(scale_score)

    scale_streak_days = _mapping(
        anomaly["scale_anomaly_streak_days"], "anomaly.scale_anomaly_streak_days"
    )
    validate_fields(
        scale_streak_days, frozenset(SCALE_NAMES), "anomaly.scale_anomaly_streak_days"
    )

    for scale in SCALE_NAMES:
        streak_days = _number(
            scale_streak_days[scale],
            f"anomaly.scale_anomaly_streak_days.{scale}",
            nullable=True,
        )
        if (streak_days is not None) != (scale in validated_scale_scores):
            raise ValueError(
                f"anomaly.scale_anomaly_streak_days.{scale} must be null exactly when anomaly.scale_scores.{scale} is null."
            )

        if streak_days is not None and streak_days < 0:
            raise ValueError(
                f"anomaly.scale_anomaly_streak_days.{scale} must not be negative."
            )

    available_scales = anomaly["available_scales"]

    if not isinstance(available_scales, list):
        raise TypeError("anomaly.available_scales must be a list.")

    expected_scales = list(validated_scale_scores)

    if available_scales != expected_scales:
        raise ValueError("anomaly.available_scales must match available scale_scores.")

    scale_deviation_pct = _mapping(
        anomaly["scale_deviation_pct"], "anomaly.scale_deviation_pct"
    )
    validate_fields(
        scale_deviation_pct,
        frozenset(DEVIATION_SCALE_NAMES),
        "anomaly.scale_deviation_pct",
    )

    for scale in DEVIATION_SCALE_NAMES:
        _number(
            scale_deviation_pct[scale],
            f"anomaly.scale_deviation_pct.{scale}",
            nullable=True,
        )

    context = _mapping(state["context"], "context")
    validate_fields(context, CONTEXT_FIELDS, "context")

    calendar_context = dict(context)
    calendar_context["decision_time"] = state["decision_time"]
    validate_calendar_context(calendar_context)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")

    return value


def _number(value: object, field_name: str, *, nullable: bool = False) -> float | None:
    if value is None:
        if nullable:
            return None

        raise ValueError(f"{field_name} must not be null.")

    if not is_real_number(value):
        raise TypeError(f"{field_name} must be numeric.")

    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite.")

    return float(value)
