from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

import pandas as pd

from src.pipeline.schema_validation import validate_fields


REQUIRED_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "event_type",
        "start",
        "end",
        "known_at",
    }
)

CALENDAR_CONTEXT_FIELDS = frozenset(
    {
        "source_available",
        "source",
        "retrieved_at",
        "decision_time",
        "window_start",
        "window_end",
        "events",
    }
)


class CalendarEvent(TypedDict):
    event_id: str
    event_type: str
    start: str
    end: str
    known_at: str


class CalendarContext(TypedDict):
    source_available: bool
    source: str
    retrieved_at: str
    decision_time: str
    window_start: str
    window_end: str
    events: list[CalendarEvent]


def validate_calendar_context(context: Mapping[str, object]) -> None:
    validate_fields(context, CALENDAR_CONTEXT_FIELDS, "Calendar context")

    if not isinstance(context["source_available"], bool):
        raise TypeError("source_available must be a boolean.")

    _normalized_non_empty_string(context["source"], "source")

    retrieved_at = _utc_timestamp(context["retrieved_at"], "retrieved_at")
    decision_time = _utc_timestamp(context["decision_time"], "decision_time")
    window_start = _utc_timestamp(context["window_start"], "window_start")
    window_end = _utc_timestamp(context["window_end"], "window_end")

    if retrieved_at > decision_time:
        raise ValueError("retrieved_at must not be after decision_time.")

    if window_start > decision_time:
        raise ValueError("window_start must not be after decision_time.")

    if window_end <= decision_time:
        raise ValueError("window_end must be after decision_time.")

    events = context["events"]
    if not isinstance(events, list):
        raise TypeError("events must be a list.")

    if not context["source_available"] and events:
        raise ValueError("Unavailable calendar source must not provide events.")

    event_ids: set[str] = set()

    for index, event_value in enumerate(events):
        if not isinstance(event_value, Mapping):
            raise TypeError(f"events[{index}] must be a mapping.")

        _validate_calendar_event(
            event_value,
            retrieved_at=retrieved_at,
            window_start=window_start,
            window_end=window_end,
            field_name=f"events[{index}]",
        )

        event_id = event_value["event_id"]
        if event_id in event_ids:
            raise ValueError(f"Duplicate calendar event_id: {event_id}")

        event_ids.add(event_id)


def _validate_calendar_event(
    event: Mapping[str, object],
    *,
    retrieved_at: pd.Timestamp,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    field_name: str = "Calendar event",
) -> None:
    validate_fields(event, REQUIRED_EVENT_FIELDS, field_name)

    event_id = _normalized_non_empty_string(event["event_id"], f"{field_name}.event_id")
    _normalized_non_empty_string(event["event_type"], f"{field_name}.event_type")

    start = _utc_timestamp(event["start"], f"{field_name}.start")
    end = _utc_timestamp(event["end"], f"{field_name}.end")
    known_at = _utc_timestamp(event["known_at"], f"{field_name}.known_at")

    if start >= end:
        raise ValueError(f"Calendar event {event_id} must end after it starts.")

    if known_at > retrieved_at:
        raise ValueError(f"Calendar event {event_id} was not known at retrieval time.")

    if start >= window_end or end <= window_start:
        raise ValueError(f"Calendar event {event_id} must overlap the context window.")


def _normalized_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace.")

    return value


def _utc_timestamp(value: object, field_name: str) -> pd.Timestamp:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string timestamp.")

    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{field_name} must be a valid timestamp.") from error

    if pd.isna(timestamp):
        raise ValueError(f"{field_name} must not be missing.")

    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must contain timezone information.")

    timestamp = timestamp.tz_convert("UTC")

    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    if normalized_value != timestamp.isoformat():
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp.")


    return timestamp