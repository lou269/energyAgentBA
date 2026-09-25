from collections.abc import Callable, Mapping

import pandas as pd

from src.common.timestamps import shift_local_days
from src.context.calendar_context import build_calendar_context
from src.context.calendar_schema import CalendarContext
from src.llm.client import ToolCall

CALENDAR_TOOL_NAME = "get_calendar_events"

# relative Tage statt Datumsangaben, das Modell muss nichts rechnen und das Fenster enthält immer decision_time
CALENDAR_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": CALENDAR_TOOL_NAME,
        "description": (
            "Returns the household's calendar events (for example absences) around the decision time. "
            "Only events that were already known at the decision time are returned."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Number of days before the decision time to include.",
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days after the decision time to include, at least 1.",
                },
            },
            "required": ["days_back", "days_ahead"],
        },
    },
}

CalendarLookup = Callable[[int, int], CalendarContext]


def lookup_calendar(
    events: tuple[Mapping[str, object], ...],
    decision_time: pd.Timestamp,
    days_back: int,
    days_ahead: int,
    *,
    source_available: bool,
    source: str,
    max_days: int,
    local_timezone: str,
) -> CalendarContext:
    days_back = min(max(days_back, 0), max_days)
    days_ahead = min(max(days_ahead, 1), max_days)

    return build_calendar_context(
        list(events),
        source_available=source_available,
        source=source,
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=shift_local_days(decision_time, -days_back, local_timezone),
        window_end=shift_local_days(decision_time, days_ahead, local_timezone),
        local_timezone=local_timezone,
    )


def requested_window(tool_calls: list[ToolCall]) -> tuple[int, int] | None:
    # mehrere Aufrufe in einer Runde: das größte Fenster gilt. Unlesbare Argumente zählen als 0
    windows = [
        (
            _whole_days(call["arguments"], "days_back"),
            _whole_days(call["arguments"], "days_ahead"),
        )
        for call in tool_calls
        if call["name"] == CALENDAR_TOOL_NAME
    ]
    if not windows:
        return None

    return max(days_back for days_back, _ in windows), max(
        days_ahead for _, days_ahead in windows
    )


def _whole_days(arguments: dict[str, object], name: str) -> int:
    try:
        return int(float(str(arguments[name])))
    except (KeyError, TypeError, ValueError):
        return 0
