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

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert result.classification == "measurement_error"


def test_single_sustained_scale_falls_back_to_peak() -> None:
    state = _state(
        direction="high",
        dominant_scale="daily",
        scale_anomaly_streak_days={"daily": 5.0, "weekday": 1.0, "long_term": 1.0},
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert result.classification == "peak"


def test_single_sustained_scale_with_low_direction_falls_back_to_low() -> None:
    state = _state(
        direction="low",
        dominant_scale="daily",
        scale_anomaly_streak_days={"daily": 5.0, "weekday": 1.0, "long_term": 1.0},
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert result.classification == "low"


def test_sustained_deviation_across_two_scales_is_a_new_pattern() -> None:
    state = _state(
        dominant_scale="daily",
        scale_anomaly_streak_days={"daily": 5.0, "weekday": 4.0, "long_term": 1.0},
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert result.classification == "new_pattern"


def test_low_direction_sustained_across_two_scales_is_also_a_new_pattern() -> None:
    state = _state(
        direction="low",
        dominant_scale="daily",
        scale_anomaly_streak_days={"daily": 5.0, "weekday": 4.0, "long_term": 1.0},
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert result.classification == "new_pattern"


def test_unsustained_anomaly_falls_back_to_peak() -> None:
    state = valid_structured_state()

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert result.classification == "peak"


def test_reasoning_mentions_weekend_on_a_saturday() -> None:
    state = valid_structured_state()
    state["decision_time"] = "2015-12-19T11:00:00+00:00"  # Samstag

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert "weekend" in result.reasoning


def test_reasoning_mentions_weekday_on_a_tuesday() -> None:
    state = valid_structured_state()

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, min_sustained_scales=2, local_timezone="UTC")

    assert "weekday" in result.reasoning
