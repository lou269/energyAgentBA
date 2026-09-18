# python -m pytest tests/unit/llm/test_rule_based_classifier.py -v

from src.llm.rule_based_classifier import rule_based_classify
from src.structured_state.structured_state_schema import StructuredState

from tests.unit.llm._state_fixture import valid_structured_state


def _state(**anomaly_overrides: object) -> StructuredState:
    state = valid_structured_state()
    state["anomaly"].update(anomaly_overrides)  # type: ignore[typeddict-item]
    return state


def _without_calendar(state: StructuredState) -> StructuredState:
    state["context"]["source_available"] = False
    state["context"]["events"] = []
    return state


def test_measurement_error_takes_priority_over_the_anomaly_pattern() -> None:
    state = valid_structured_state()
    state["observation"]["value_implausible"] = True

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "measurement_error"


def test_measurement_error_takes_priority_over_a_calendar_absence_event() -> None:
    state = valid_structured_state()  # deckt decision_time schon über sein eingebautes Event ab
    state["observation"]["value_implausible"] = True

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "measurement_error"


def test_calendar_absence_event_covering_decision_time_is_an_absence() -> None:
    state = valid_structured_state()

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "absence"


def test_calendar_event_of_a_different_type_is_not_an_absence() -> None:
    state = valid_structured_state()
    state["context"]["events"][0]["event_type"] = "other"

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification != "absence"


def test_calendar_absence_event_outside_its_window_is_not_an_absence() -> None:
    state = valid_structured_state()
    state["decision_time"] = "2015-12-25T11:00:00+00:00"  # nach event.end (2015-12-22)

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification != "absence"


def test_sustained_low_deviation_without_calendar_event_is_not_an_absence() -> None:
    state = _without_calendar(
        _state(
            direction="low",
            dominant_scale="daily",
            scale_anomaly_streak_days={"daily": 5.0, "weekday": 1.0, "long_term": 1.0},
        )
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "peak"


def test_sustained_deviation_across_two_scales_is_a_new_pattern() -> None:
    state = _without_calendar(
        _state(
            dominant_scale="daily",
            scale_anomaly_streak_days={"daily": 5.0, "weekday": 4.0, "long_term": 1.0},
        )
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "new_pattern"


def test_low_direction_sustained_across_two_scales_is_also_a_new_pattern() -> None:
    state = _without_calendar(
        _state(
            direction="low",
            dominant_scale="daily",
            scale_anomaly_streak_days={"daily": 5.0, "weekday": 4.0, "long_term": 1.0},
        )
    )

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "new_pattern"


def test_unsustained_anomaly_falls_back_to_peak() -> None:
    state = _without_calendar(valid_structured_state())

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert result.classification == "peak"


def test_reasoning_mentions_weekend_on_a_saturday() -> None:
    state = _without_calendar(valid_structured_state())
    state["decision_time"] = "2015-12-19T11:00:00+00:00"  # Samstag

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert "weekend" in result.reasoning


def test_reasoning_mentions_weekday_on_a_tuesday() -> None:
    state = _without_calendar(valid_structured_state())

    result = rule_based_classify(state, sustained_anomaly_streak_days=3, multi_scale_minimum=2, local_timezone="UTC")

    assert "weekday" in result.reasoning