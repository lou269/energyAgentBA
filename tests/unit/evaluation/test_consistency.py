# python -m pytest tests/unit/evaluation/test_consistency.py -v

from src.evaluation.consistency import missing_evidence_paths
from tests.unit.llm._state_fixture import valid_structured_state

BASE_PATHS = ["anomaly.level"]


def test_evidence_per_class() -> None:
    state = valid_structured_state()
    state["anomaly"]["sustained_scales"] = ["weekday", "long_term"]

    assert missing_evidence_paths("peak", BASE_PATHS, state) == ("anomaly.direction",)
    assert missing_evidence_paths(
        "new_pattern",
        ["anomaly.scale_anomaly_streak_days.weekday"],
        state,
    ) == ("anomaly.scale_anomaly_streak_days.long_term",)
    assert (
        missing_evidence_paths(
            "measurement_error", ["observation.value_implausible"], state
        )
        == ()
    )


def test_absence_needs_event() -> None:
    state = valid_structured_state()

    assert missing_evidence_paths("absence", BASE_PATHS, state) == (
        "context.events.<index>.event_type",
    )
    assert (
        missing_evidence_paths(
            "absence", BASE_PATHS + ["context.events.0.event_type"], state
        )
        == ()
    )
