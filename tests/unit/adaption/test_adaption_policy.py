# python -m pytest tests/unit/adaption/test_adaption_policy.py -v


from typing import Any, cast

import pandas as pd
import pytest

from src.adaption.adaption_policy import adaption_policy
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# minimaler Kontext, adaption_policy liest nur observation.observation_start, decision_time und anomaly.dominant_scale/scale_anomaly_streak_days/available_scales
def _context(
    *,
    decision_time: str,
    dominant_scale: str | None,
    streak_days: float | None = None,
    scale_streak_days: dict[str, float | None] | None = None,
) -> StructuredState:
    if scale_streak_days is None:
        scale_streak_days = {dominant_scale: streak_days} if dominant_scale else {}

    return cast(
        StructuredState,
        {
            "decision_time": decision_time,
            "observation": {"observation_start": "2024-01-07T09:00:00+00:00"},
            "anomaly": {
                "dominant_scale": dominant_scale,
                "scale_anomaly_streak_days": scale_streak_days,
                "available_scales": list(scale_streak_days.keys()),
            },
        },
    )


def test_measurement_error_excludes_exactly_the_observation_hour() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale=None, streak_days=None)

    action = adaption_policy("measurement_error", context, sustained_anomaly_streak_days=2)

    assert action.kind == "exclude_range"
    assert action.range_start == action.range_end
    assert action.range_start is not None
    assert action.range_start.isoformat() == "2024-01-07T09:00:00+00:00"


def test_absence_excludes_the_streak_length_in_hours() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale="daily", streak_days=2)

    action = adaption_policy("absence", context, sustained_anomaly_streak_days=2)

    assert action.kind == "exclude_range"
    assert action.range_start is not None and action.range_end is not None
    # 2 Tage Streak, endet bei decision_time - 1h -> Fensterstart ist 47h davor
    assert action.range_start.isoformat() == "2024-01-05T10:00:00+00:00"
    assert action.range_end.isoformat() == "2024-01-07T09:00:00+00:00"


def test_new_pattern_advances_the_history_start_by_the_streak_length() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale="weekly", streak_days=2)

    action = adaption_policy("new_pattern", context, sustained_anomaly_streak_days=2)

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None
    assert action.new_history_start.isoformat() == "2024-01-05T10:00:00+00:00"


def test_new_pattern_ignores_a_dominant_scale_that_is_not_sustained() -> None:
    context = _context(
        decision_time="2024-01-07T10:00:00+00:00",
        dominant_scale="long_term",
        scale_streak_days={"daily": 8, "weekly": 10, "long_term": 2},
    )

    action = adaption_policy("new_pattern", context, sustained_anomaly_streak_days=7)

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None

    range_end = pd.Timestamp("2024-01-07T09:00:00+00:00")
    expected_start = range_end - pd.Timedelta(hours=8 * 24 - 1)
    assert action.new_history_start == expected_start


@pytest.mark.parametrize("classification", ["peak", "normal", "unknown"])
def test_classifications_without_a_defined_reaction_trigger_no_action(classification: Classification) -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00", dominant_scale=None, streak_days=None)

    action = adaption_policy(classification, context, sustained_anomaly_streak_days=2)

    assert action.kind == "none"

