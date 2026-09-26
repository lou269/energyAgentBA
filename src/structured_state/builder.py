import math
from numbers import Real
from typing import TypeVar, cast

import numpy as np
import pandas as pd

from src.common.timestamps import local_isoformat, parse_utc_timestamp
from src.context.calendar_schema import CalendarContext
from src.pipeline.schema_validation import is_real_number
from src.structured_state.structured_state_schema import (
    ANOMALY_DIRECTIONS,
    ANOMALY_LEVELS,
    SCALE_NAMES,
    SCHEMA_VERSION,
    ContextState,
    ScaleAnomalyStreakDays,
    ScaleDeviationPct,
    ScaleName,
    ScaleScores,
    StructuredState,
)


ANALYSIS_FIELDS = frozenset(
    {
        "timestamp",
        "weekday_deviation_pct",
        "weekly_deviation_pct",
        "long_term_deviation_pct",
        "daily_score",
        "weekday_score",
        "weekly_score",
        "long_term_score",
        "daily_anomaly_streak_days",
        "weekday_anomaly_streak_days",
        "weekly_anomaly_streak_days",
        "long_term_anomaly_streak_days",
        "daily_sustained",
        "weekday_sustained",
        "weekly_sustained",
        "long_term_sustained",
        "sustained_drift",
        "anomaly_direction",
        "anomaly_level",
        "value_implausible",
    }
)

TextType = TypeVar("TextType", bound=str)


# der State trägt den Kalender ohne decision_time, die steht schon oben im State
def context_state(calendar_context: CalendarContext) -> ContextState:
    return {
        "source_available": calendar_context["source_available"],
        "source": calendar_context["source"],
        "retrieved_at": calendar_context["retrieved_at"],
        "window_start": calendar_context["window_start"],
        "window_end": calendar_context["window_end"],
        "events": list(calendar_context["events"]),
    }


def build_structured_state(
    *,
    decision_time: str | pd.Timestamp,
    analysis_row: pd.Series,
    calendar_context: CalendarContext,
    local_timezone: str,
) -> StructuredState:
    decision_time = parse_utc_timestamp(decision_time, "decision_time")

    missing = ANALYSIS_FIELDS.difference(analysis_row.index)
    if missing:
        raise ValueError(
            "Analysis row is missing required fields: " + ", ".join(sorted(missing))
        )

    analysis_timestamp = parse_utc_timestamp(
        analysis_row["timestamp"], "analysis.timestamp"
    )

    if analysis_timestamp >= decision_time:
        raise ValueError("Analysis timestamp must be before decision_time.")

    context_decision_time = parse_utc_timestamp(
        calendar_context["decision_time"], "calendar_context.decision_time"
    )

    if context_decision_time != decision_time:
        raise ValueError("Calendar context decision_time must match decision_time.")

    scale_scores: ScaleScores = {
        "daily": _nullable_float(analysis_row["daily_score"], "analysis.daily_score"),
        "weekday": _nullable_float(
            analysis_row["weekday_score"], "analysis.weekday_score"
        ),
        "weekly": _nullable_float(
            analysis_row["weekly_score"], "analysis.weekly_score"
        ),
        "long_term": _nullable_float(
            analysis_row["long_term_score"], "analysis.long_term_score"
        ),
    }

    scale_streak_days: ScaleAnomalyStreakDays = {
        "daily": _nullable_float(
            analysis_row["daily_anomaly_streak_days"],
            "analysis.daily_anomaly_streak_days",
        ),
        "weekday": _nullable_float(
            analysis_row["weekday_anomaly_streak_days"],
            "analysis.weekday_anomaly_streak_days",
        ),
        "weekly": _nullable_float(
            analysis_row["weekly_anomaly_streak_days"],
            "analysis.weekly_anomaly_streak_days",
        ),
        "long_term": _nullable_float(
            analysis_row["long_term_anomaly_streak_days"],
            "analysis.long_term_anomaly_streak_days",
        ),
    }

    scale_deviation_pct: ScaleDeviationPct = {
        "weekday": _nullable_float(
            analysis_row["weekday_deviation_pct"], "analysis.weekday_deviation_pct"
        ),
        "weekly": _nullable_float(
            analysis_row["weekly_deviation_pct"], "analysis.weekly_deviation_pct"
        ),
        "long_term": _nullable_float(
            analysis_row["long_term_deviation_pct"], "analysis.long_term_deviation_pct"
        ),
    }

    available_scales: list[ScaleName] = [
        scale for scale in SCALE_NAMES if scale_scores[scale] is not None
    ]

    sustained_scales: list[ScaleName] = [
        scale
        for scale in SCALE_NAMES
        if _bool(analysis_row[f"{scale}_sustained"], f"analysis.{scale}_sustained")
    ]

    state: StructuredState = {
        "schema_version": SCHEMA_VERSION,
        "decision_time": local_isoformat(decision_time, local_timezone),
        "observation": {
            "observation_start": local_isoformat(analysis_timestamp, local_timezone),
            "observation_end": local_isoformat(decision_time, local_timezone),
            "value_implausible": _bool(
                analysis_row["value_implausible"], "analysis.value_implausible"
            ),
        },
        "anomaly": {
            "level": _nullable_text(
                analysis_row["anomaly_level"], "anomaly.level", ANOMALY_LEVELS
            ),
            "direction": _nullable_text(
                analysis_row["anomaly_direction"],
                "anomaly.direction",
                ANOMALY_DIRECTIONS,
            ),
            "scale_scores": scale_scores,
            "scale_anomaly_streak_days": scale_streak_days,
            "scale_deviation_pct": scale_deviation_pct,
            "sustained_scales": sustained_scales,
            "sustained_drift": _bool(
                analysis_row["sustained_drift"], "analysis.sustained_drift"
            ),
            "available_scales": available_scales,
        },
        "context": context_state(calendar_context),
    }

    return state


def _nullable_float(value: object, field_name: str) -> float | None:
    if _is_missing(value):
        return None

    if not is_real_number(value):
        raise TypeError(f"{field_name} must be numeric or null.")

    number = float(value)

    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")

    return number


def _nullable_text(
    value: object, field_name: str, allowed: tuple[TextType, ...]
) -> TextType | None:
    if _is_missing(value):
        return None

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or null.")

    if value not in allowed:
        raise ValueError(f"{field_name} contains an unsupported value.")

    return cast(TextType, value)


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
