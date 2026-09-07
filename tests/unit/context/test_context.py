# python -m pytest tests/unit/test_context.py -v

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from src.context.calendar_context import build_calendar_context
from src.context.calendar_schema import CalendarContext, validate_calendar_context


DECISION_TIME = "2013-09-02T00:00:00+00:00"

EVENT = {
    "event_id": "absence",
    "event_type": "absence",
    "start": "2013-09-01T08:00:00+00:00",
    "end": "2013-09-01T20:00:00+00:00",
    "known_at": "2013-08-30T00:00:00+00:00",
}


def _build_context(
    events: list[Mapping[str, object]] | None = None,
    *,
    source_available: bool = True,
    retrieved_at: str = DECISION_TIME,
    decision_time: str = DECISION_TIME,
    window_start: str = "2013-09-01T00:00:00+00:00",
    window_end: str = "2013-09-03T00:00:00+00:00",
) -> CalendarContext:
    return build_calendar_context(
        events or [],
        source_available=source_available,
        source="simulated_calendar",
        retrieved_at=retrieved_at,
        decision_time=decision_time,
        window_start=window_start,
        window_end=window_end,
    )


def test_calendar_context_normalizes_timestamps_to_utc() -> None:
    context = _build_context(
        [
            {
                **EVENT,
                "start": "2013-09-01T09:00:00+01:00",
                "end": "2013-09-01T21:00:00+01:00",
                "known_at": "2013-08-30T01:00:00+01:00",
            }
        ],
        retrieved_at="2013-09-02T01:00:00+01:00",
        decision_time="2013-09-02T01:00:00+01:00",
        window_start="2013-09-01T01:00:00+01:00",
        window_end="2013-09-03T01:00:00+01:00",
    )

    assert context["decision_time"] == DECISION_TIME
    assert context["events"][0]["start"] == "2013-09-01T08:00:00+00:00"
    assert context["events"][0]["known_at"] == "2013-08-30T00:00:00+00:00"


def test_calendar_context_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone information"):
        _build_context(decision_time="2013-09-02T00:00:00")


def test_calendar_context_rejects_invalid_time_order() -> None:
    with pytest.raises(ValueError, match="retrieved_at must not be after"):
        _build_context(retrieved_at="2013-09-02T01:00:00+00:00")

    with pytest.raises(ValueError, match="window_start must not be after"):
        _build_context(window_start="2013-09-02T01:00:00+00:00")

    with pytest.raises(ValueError, match="window_end must be after"):
        _build_context(window_end=DECISION_TIME)


def test_calendar_context_filters_causally_and_uses_half_open_window() -> None:
    context = _build_context(
        [
            {
                **EVENT,
                "event_id": "future-known",
                "start": "2013-09-02T12:00:00+00:00",
                "end": "2013-09-02T18:00:00+00:00",
            },
            {
                **EVENT,
                "event_id": "future-unknown",
                "known_at": "2013-09-02T01:00:00+00:00",
            },
            {
                **EVENT,
                "event_id": "before-window",
                "start": "2013-08-31T12:00:00+00:00",
                "end": "2013-09-01T00:00:00+00:00",
            },
            {**EVENT, "event_id": "recently-ended"},
            {
                **EVENT,
                "event_id": "after-window",
                "start": "2013-09-03T00:00:00+00:00",
                "end": "2013-09-03T12:00:00+00:00",
            },
        ]
    )

    assert [event["event_id"] for event in context["events"]] == [
        "recently-ended",
        "future-known",
    ]


def test_calendar_context_rejects_duplicate_event_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate calendar event_id"):
        _build_context([EVENT, EVENT])


def test_calendar_context_distinguishes_empty_and_unavailable_source() -> None:
    available = _build_context()
    unavailable = _build_context(source_available=False)

    assert available["source_available"] is True
    assert unavailable["source_available"] is False
    assert available["events"] == unavailable["events"] == []

    with pytest.raises(ValueError, match="must not provide events"):
        _build_context([EVENT], source_available=False)


def test_loaded_calendar_context_is_fully_revalidated() -> None:
    loaded_context = json.loads(json.dumps(_build_context([EVENT])))
    loaded_context["events"][0]["known_at"] = "2013-09-02T01:00:00+00:00"

    with pytest.raises(ValueError, match="not known at retrieval time"):
        validate_calendar_context(loaded_context)
