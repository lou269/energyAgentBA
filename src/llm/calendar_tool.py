from collections.abc import Callable

from src.context.calendar_schema import CalendarContext
from src.llm.client import ToolCall

CALENDAR_TOOL_NAME = "get_calendar_events"

# ohne Argumente: ein Aufruf liefert dasselbe Fenster wie bei CTX1, CTX2 unterscheidet sich nur darin, ob das LLM nachschaut
CALENDAR_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": CALENDAR_TOOL_NAME,
        "description": (
            "Returns the household's calendar events around the analyzed day. "
            "Only events that were already known at the decision time are returned. "
            "Use this tool only when calendar events during the observed change "
            "could help distinguish between plausible explanations."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

CalendarLookup = Callable[[], CalendarContext]


def calendar_requested(tool_calls: list[ToolCall]) -> bool:
    return any(call["name"] == CALENDAR_TOOL_NAME for call in tool_calls)
