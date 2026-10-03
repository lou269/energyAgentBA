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

    result = rule_based_classify(state, local_timezone="UTC", min_sustained_scales=2)

    assert result.classification == "measurement_error"


def test_below_the_scale_minimum_the_direction_decides_between_peak_and_low() -> None:
    # eine einzelne sustained Skala ist noch keine Drift
    for direction, expected in (("high", "peak"), ("low", "low")):
        state = _state(direction=direction, sustained_scales=["weekly"])

        result = rule_based_classify(
            state, local_timezone="UTC", min_sustained_scales=2
        )

        assert result.classification == expected


def test_one_sustained_scale_on_a_normal_day_is_normal() -> None:
    for direction in ("high", "low"):
        state = _state(level="normal", direction=direction, sustained_scales=["weekly"])

        result = rule_based_classify(
            state, local_timezone="UTC", min_sustained_scales=2
        )

        assert result.classification == "normal"


def test_enough_sustained_scales_are_a_new_pattern_in_both_directions() -> None:
    for direction in ("high", "low"):
        state = _state(direction=direction, sustained_scales=["weekday", "weekly"])

        result = rule_based_classify(
            state, local_timezone="UTC", min_sustained_scales=2
        )

        assert result.classification == "new_pattern"


def test_drift_is_a_new_pattern_even_if_today_is_unremarkable() -> None:
    state = _state(level="normal", sustained_scales=["weekly", "long_term"])

    result = rule_based_classify(state, local_timezone="UTC", min_sustained_scales=2)

    assert result.classification == "new_pattern"


def test_reasoning_mentions_weekend_on_a_saturday() -> None:
    state = valid_structured_state()
    state["decision_time"] = "2015-12-20T00:00:00+00:00"  # analysierter Tag ist Samstag

    result = rule_based_classify(state, local_timezone="UTC", min_sustained_scales=2)

    assert "weekend" in result.reasoning


def test_reasoning_mentions_weekday_on_a_tuesday() -> None:
    state = valid_structured_state()

    result = rule_based_classify(state, local_timezone="UTC", min_sustained_scales=2)

    assert "weekday" in result.reasoning
