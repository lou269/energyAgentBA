from __future__ import annotations

from typing import TypedDict


REQUIRED_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "event_type",
        "start",
        "end",
        "known_at",
    }
)

ALLOWED_EVENT_FIELDS = REQUIRED_EVENT_FIELDS | {"status"}

CALENDAR_CONTEXT_FIELDS = frozenset(
    {
        "source_available",
        "source",
        "retrieved_at",
        "decision_time",
        "window_end",
        "events",
    }
)


class _RequiredCalendarEvent(TypedDict):
    event_id: str
    event_type: str
    start: str
    end: str
    known_at: str


class CalendarEvent(_RequiredCalendarEvent, total=False):
    status: str


class CalendarContext(TypedDict):
    source_available: bool
    source: str
    retrieved_at: str
    decision_time: str
    window_end: str
    events: list[CalendarEvent]