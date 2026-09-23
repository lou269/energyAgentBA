# python -m pytest tests/unit/adaption/test_adaption_policy.py -v


from typing import cast

import pytest

from src.adaption.adaption_policy import adaption_policy
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# minimaler Kontext, adaption_policy liest nur decision_time
def _context(*, decision_time: str) -> StructuredState:
    return cast(
        StructuredState,
        {
            "decision_time": decision_time,
        },
    )


def test_new_pattern_advances_the_history_start_by_the_tolerance_window() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00")

    action = adaption_policy("new_pattern", context, streak_tolerance_window_days=2, local_timezone="UTC")

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None
    # 2 Kalendertage vor decision_time
    assert action.new_history_start.isoformat() == "2024-01-05T10:00:00+00:00"


@pytest.mark.parametrize("classification", ["peak", "normal", "unknown", "absence", "measurement_error"])
def test_classifications_without_a_defined_reaction_trigger_no_action(classification: Classification) -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00")

    action = adaption_policy(classification, context, streak_tolerance_window_days=7, local_timezone="UTC")

    assert action.kind == "none"
