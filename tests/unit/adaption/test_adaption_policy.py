# python -m pytest tests/unit/adaption/test_adaption_policy.py -v


from typing import cast

import pandas as pd
import pytest

from src.adaption.adaption_policy import adaption_policy, mask_excluded_windows
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# minimaler Kontext, adaption_policy liest nur decision_time und die Kalendereinträge
def _context(*, decision_time: str, events: list[dict] | None = None) -> StructuredState:
    return cast(
        StructuredState,
        {
            "decision_time": decision_time,
            "context": {"events": events or []},
        },
    )


def _event(event_type: str) -> dict:
    return {
        "event_id": "vacation-test",
        "event_type": event_type,
        "start": "2013-09-14T00:00:00+00:00",
        "end": "2013-09-28T00:00:00+00:00",
        "known_at": "2013-08-14T00:00:00+00:00",
    }


def test_new_pattern_advances_the_history_start_by_the_tolerance_window() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00")

    action = adaption_policy("new_pattern", context, streak_tolerance_window_days=2, local_timezone="UTC")

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None
    # 2 Kalendertage vor decision_time
    assert action.new_history_start.isoformat() == "2024-01-05T10:00:00+00:00"


@pytest.mark.parametrize("classification", ["peak", "normal", "unknown", "measurement_error"])
def test_classifications_without_a_defined_reaction_trigger_no_action(classification: Classification) -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00")

    action = adaption_policy(classification, context, streak_tolerance_window_days=7, local_timezone="UTC")

    assert action.kind == "none"


def test_absence_excludes_the_whole_calendar_window_not_only_the_analyzed_day() -> None:
    # erkannt erst am 26.09., ausgeschlossen wird trotzdem ab dem 14.09.
    context = _context(decision_time="2013-09-27T00:00:00+00:00", events=[_event("absence")])

    action = adaption_policy("absence", context, streak_tolerance_window_days=7, local_timezone="UTC")

    assert action.kind == "exclude_window"
    assert action.excluded_window == (
        pd.Timestamp("2013-09-14T00:00:00+00:00"),
        pd.Timestamp("2013-09-28T00:00:00+00:00"),
    )


@pytest.mark.parametrize(
    ("decision_time", "event_type"),
    [
        ("2013-09-27T00:00:00+00:00", "business_trip"),
        # analysierter Tag 28.09. liegt schon hinter dem Ende
        ("2013-09-29T00:00:00+00:00", "absence"),
    ],
)
def test_absence_without_a_matching_calendar_event_triggers_no_action(decision_time: str, event_type: str) -> None:
    context = _context(decision_time=decision_time, events=[_event(event_type)])

    action = adaption_policy("absence", context, streak_tolerance_window_days=7, local_timezone="UTC")

    assert action.kind == "none"


def test_mask_excluded_windows_keeps_the_analyzed_day_and_everything_outside() -> None:
    index = pd.date_range("2013-09-13", periods=4 * 24, freq="1h", tz="UTC")
    history = pd.Series(100.0, index=index)
    window = (pd.Timestamp("2013-09-14", tz="UTC"), pd.Timestamp("2013-09-28", tz="UTC"))

    masked = mask_excluded_windows(history, (window,), keep_from=pd.Timestamp("2013-09-16", tz="UTC"))

    daily_valid = masked.notna().groupby(masked.index.date).sum()
    assert daily_valid.tolist() == [24, 0, 0, 24]
