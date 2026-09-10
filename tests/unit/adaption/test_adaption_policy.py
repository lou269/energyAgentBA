# python -m pytest tests/unit/adaption/test_adaption_policy.py -v


from typing import Any, cast

import pytest

from src.adaption.adaption_policy import adaption_policy
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# minimaler Kontext - adaption_policy liest nur observation.observation_start, decision_time und anomaly.dominant_scale/scale_streak_hours, 
def _context(
    *, 
    decision_time: str, 
    dominant_scale: str | None, 
    streak_hours: float | None
) -> StructuredState:
    return cast(
        StructuredState,
        {
            "decision_time": decision_time,
            "observation": {"observation_start": "2024-01-07T09:00:00+00:00"},
            "anomaly": {
                "dominant_scale": dominant_scale,
                "scale_streak_hours": {dominant_scale: streak_hours} if dominant_scale else {},
            },
        },
    )


def test_measurement_error_excludes_exactly_the_observation_hour() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale=None, streak_hours=None)

    action = adaption_policy("measurement_error", context)

    assert action.kind == "exclude_range"
    assert action.range_start == action.range_end
    assert action.range_start is not None
    assert action.range_start.isoformat() == "2024-01-07T09:00:00+00:00"


def test_absence_excludes_the_dominant_scale_streak_up_to_decision_time() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale="daily", streak_hours=30.0)

    action = adaption_policy("absence", context)

    assert action.kind == "exclude_range"
    assert action.range_start is not None and action.range_end is not None
    assert action.range_start.isoformat() == "2024-01-06T04:00:00+00:00"
    assert action.range_end.isoformat() == "2024-01-07T09:00:00+00:00"


def test_new_pattern_advances_the_history_start_by_the_dominant_scale_streak() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale="short_term", streak_hours=24.0)

    action = adaption_policy("new_pattern", context)

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None
    assert action.new_history_start.isoformat() == "2024-01-06T10:00:00+00:00"


@pytest.mark.parametrize("classification", ["peak", "normal", "unknown"])
def test_classifications_without_a_defined_reaction_trigger_no_action(classification: Classification) -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale=None, streak_hours=None)

    action = adaption_policy(classification, context)

    assert action.kind == "none"

