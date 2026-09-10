# python -m pytest tests/unit/llm/test_rule_based_classifier.py -v

from src.llm.rule_based_classifier import rule_based_classify
from src.structured_state.structured_state_schema import StructuredState

from tests.unit.llm._state_fixture import valid_structured_state


def _state(**anomaly_overrides: object) -> StructuredState:
    state = valid_structured_state()
    state["anomaly"].update(anomaly_overrides)  # type: ignore[typeddict-item]
    return state


def test_measurement_error_takes_priority_over_the_anomaly_pattern() -> None:
    state = valid_structured_state()
    state["observation"]["value_implausible"] = True

    result = rule_based_classify(state)

    assert result.classification == "measurement_error"


def test_strong_sustained_low_deviation_is_an_absence() -> None:
    state = _state(
        direction="low",
        dominant_scale="daily",
        scale_streak_hours={"short_term": 1.0, "daily": 30.0, "weekly": 1.0, "long_term": 1.0},
    )

    result = rule_based_classify(state)

    assert result.classification == "absence"


def test_sustained_deviation_across_two_scales_is_a_new_pattern() -> None:
    # direction bleibt "high" (Basiszustand) - sonst greift  absence-Regel zuerst
    state = _state(
        dominant_scale="daily",
        scale_streak_hours={"short_term": 1.0, "daily": 30.0, "weekly": 25.0, "long_term": 1.0},
    )

    result = rule_based_classify(state)

    assert result.classification == "new_pattern"


def test_unsustained_anomaly_falls_back_to_peak() -> None:
    # unveränderter Fixture-Zustand: strong_anomaly, aber alle scale_streak_hours nur 1.0
    state = valid_structured_state()

    result = rule_based_classify(state)

    assert result.classification == "peak"
