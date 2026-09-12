# python -m pytest tests/unit/adaption/test_adaption_policy.py -v


from typing import Any, cast

import pytest

from src.adaption.adaption_policy import adaption_policy
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# minimaler Kontext - adaption_policy liest nur observation.observation_start, decision_time und anomaly.dominant_scale/scale_elevated_hours
def _context(
    *, 
    decision_time: str,
    dominant_scale: str | None, 
    elevated_hours: float | None
) -> StructuredState:
    return cast(
        StructuredState,
        {
            "decision_time": decision_time,
            "observation": {"observation_start": "2024-01-07T09:00:00+00:00"},
            "anomaly": {
                "dominant_scale": dominant_scale,
                "scale_elevated_hours": {dominant_scale: elevated_hours} if dominant_scale else {},
            },
        },
    )


def test_measurement_error_excludes_exactly_the_observation_hour() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale=None, elevated_hours=None)

    action = adaption_policy("measurement_error", context, anomaly_window_hours=24)

    assert action.kind == "exclude_range"
    assert action.range_start == action.range_end
    assert action.range_start is not None
    assert action.range_start.isoformat() == "2024-01-07T09:00:00+00:00"


def test_absence_excludes_the_analyzed_24h_window() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale="daily", elevated_hours=20.0)

    action = adaption_policy("absence", context, anomaly_window_hours=24)

    assert action.kind == "exclude_range"
    assert action.range_start is not None and action.range_end is not None
    # anomaly_window_hours=24, endet bei decision_time - 1h -> Fensterstart ist 23h davor
    assert action.range_start.isoformat() == "2024-01-06T10:00:00+00:00"
    assert action.range_end.isoformat() == "2024-01-07T09:00:00+00:00"


def test_new_pattern_advances_the_history_start_to_the_analyzed_24h_window() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale="short_term", elevated_hours=18.0)

    action = adaption_policy("new_pattern", context, anomaly_window_hours=24)

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None
    assert action.new_history_start.isoformat() == "2024-01-06T10:00:00+00:00"


@pytest.mark.parametrize("classification", ["peak", "normal", "unknown"])
def test_classifications_without_a_defined_reaction_trigger_no_action(classification: Classification) -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale=None, elevated_hours=None)

    action = adaption_policy(classification, context, anomaly_window_hours=24)

    assert action.kind == "none"

