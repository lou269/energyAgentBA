from collections.abc import Mapping

import pandas as pd

from src.common.timestamps import local_isoformat, parse_utc_timestamp
from src.context.calendar_schema import (
    REQUIRED_EVENT_FIELDS,
    CalendarContext,
    CalendarEvent,
    validate_calendar_context,
    validate_fields,
)


def build_calendar_context(
    events: list[Mapping[str, object]],
    *,
    source_available: bool,
    source: str,
    retrieved_at: str | pd.Timestamp,
    decision_time: str | pd.Timestamp,
    window_start: str | pd.Timestamp,
    window_end: str | pd.Timestamp,
    local_timezone: str,
) -> CalendarContext:
    """
    Überführt bereits abgerufene Kalenderereignisse in kausal verfügbaren Kontext.

    Kontext- und Ereignisintervalle werden als [start, end) interpretiert.
    Informationen, die beim Abruf noch nicht bekannt waren, werden nicht weitergegeben.
    """

    if not isinstance(source_available, bool):
        raise TypeError("source_available must be a boolean.")

    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string.")

    if not isinstance(events, list):
        raise TypeError("events must be a list.")

    source = source.strip()
    retrieved_at = parse_utc_timestamp(retrieved_at, "retrieved_at")
    decision_time = parse_utc_timestamp(decision_time, "decision_time")
    window_start = parse_utc_timestamp(window_start, "window_start")
    window_end = parse_utc_timestamp(window_end, "window_end")

    if retrieved_at > decision_time:
        raise ValueError("retrieved_at must not be after decision_time.")

    if window_start > decision_time:
        raise ValueError("window_start must not be after decision_time.")

    if window_end <= decision_time:
        raise ValueError("window_end must be after decision_time.")

    context: CalendarContext = {
        "source_available": source_available,
        "source": source,
        "retrieved_at": local_isoformat(retrieved_at, local_timezone),
        "decision_time": local_isoformat(decision_time, local_timezone),
        "window_start": local_isoformat(window_start, local_timezone),
        "window_end": local_isoformat(window_end, local_timezone),
        "events": [],
    }

    if not source_available:
        if events:
            raise ValueError("Unavailable calendar source must not provide events.")

        validate_calendar_context(context)
        return context

    normalized_events: list[tuple[pd.Timestamp, pd.Timestamp, CalendarEvent]] = []
    event_ids: set[str] = set()

    for event in events:
        if not isinstance(event, Mapping):
            raise TypeError("Each event must be a mapping.")

        validate_fields(event, REQUIRED_EVENT_FIELDS, "Calendar event")

        event_id = event["event_id"]
        event_type = event["event_type"]

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a non-empty string.")

        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")

        event_id = event_id.strip()
        event_type = event_type.strip()

        if event_id in event_ids:
            raise ValueError(f"Duplicate calendar event_id: {event_id}")

        event_ids.add(event_id)

        start = parse_utc_timestamp(event["start"], "start")
        end = parse_utc_timestamp(event["end"], "end")
        known_at = parse_utc_timestamp(event["known_at"], "known_at")

        if start >= end:
            raise ValueError(f"Calendar event {event_id} must end after it starts.")

        if known_at > retrieved_at:
            continue

        if start >= window_end or end <= window_start:
            continue

        normalized_events.append(
            (
                start,
                end,
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "start": local_isoformat(start, local_timezone),
                    "end": local_isoformat(end, local_timezone),
                    "known_at": local_isoformat(known_at, local_timezone),
                },
            )
        )

    # nach Zeitpunkt statt nach String sortieren, Sommer- und Winterzeit haben unterschiedliche Offsets
    normalized_events.sort(key=lambda item: (item[0], item[1], item[2]["event_id"]))

    context["events"] = [event for _start, _end, event in normalized_events]
    validate_calendar_context(context)

    return context