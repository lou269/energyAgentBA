# python -m pytest tests/unit/proposal_experiments/e2_absence/test_e2_selection.py -v

import pandas as pd
import pytest

from experiments.proposal_experiments.e2_absence.e2_config import ACTIVE_ABSENCE_EVENT_ID,CALENDAR_EVENTS_FILE
from experiments.proposal_experiments.e2_absence.e2_selection import build_decision_times, load_calendar_events, resolve_absence_window



def test_load_calendar_events_includes_the_active_absence_window() -> None:
   
    events = load_calendar_events(CALENDAR_EVENTS_FILE)
    events_by_id = {event["event_id"]: event for event in events}

    assert ACTIVE_ABSENCE_EVENT_ID in events_by_id
    event = events_by_id[ACTIVE_ABSENCE_EVENT_ID]
    assert event["event_type"] == "absence"
    # muss vor Fensterbeginn feststehen, sonst würde build_calendar_context rausfiltern
    assert str(event["known_at"]) < str(event["start"])


def test_resolve_absence_window_matches_e2_config_reference() -> None:
    events = load_calendar_events(CALENDAR_EVENTS_FILE)

    window_start, window_end = resolve_absence_window(events, ACTIVE_ABSENCE_EVENT_ID)

    assert window_start == pd.Timestamp("2013-06-06T00:00:00+00:00")
    assert window_end == pd.Timestamp("2013-06-13T00:00:00+00:00")


def test_resolve_absence_window_raises_for_unknown_event_id() -> None:
    events = ({"event_id": "known", "start": "2020-01-01T00:00:00+00:00", "end": "2020-01-02T00:00:00+00:00"},)

    with pytest.raises(ValueError, match="unknown"):
        resolve_absence_window(events, "unknown")


def test_build_decision_times_applies_margins_on_both_sides() -> None:
    window_start = pd.Timestamp("2020-06-06T00:00:00+00:00")
    window_end = pd.Timestamp("2020-06-13T00:00:00+00:00")

    decision_times = build_decision_times(window_start, window_end, margin_before_days=7, margin_after_days=4)

    assert decision_times[0] == window_start - pd.Timedelta(days=7)
    assert decision_times[-1] == window_end + pd.Timedelta(days=4)
    assert all(second - first == pd.Timedelta(hours=24) for first, second in zip(decision_times, decision_times[1:]))