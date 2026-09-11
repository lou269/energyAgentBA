from __future__ import annotations

from pathlib import Path

CALENDAR_EVENTS_FILE = Path(__file__).resolve().parents[2] / "scenarios" / "calendar_events.json"

# welches Event aus calendar_events.json aktuell als Zielwoche 
ACTIVE_ABSENCE_EVENT_ID = "vacation-2013-06"

DECISION_TIME_MARGIN_BEFORE_DAYS = 7
DECISION_TIME_MARGIN_AFTER_DAYS = 4

COLDSTART_HOURS = 168

MIN_COVERAGE_SHARE_FOR_SUBTRACTION = 0.9
MIN_ACTIVITY_SHARE_FOR_SUBTRACTION = 0.05