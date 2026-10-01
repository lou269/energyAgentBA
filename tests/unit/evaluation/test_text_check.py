# python -m pytest tests/unit/evaluation/test_text_check.py -v

from src.config.config_forecasting import TextCheckConfig
from src.evaluation.text_check import (
    TextViolation,
    collect_state_values,
    find_violations,
)
from tests.unit.llm._state_fixture import valid_structured_state


def _check(text: str) -> tuple[TextViolation, ...]:
    config = TextCheckConfig()
    quantities, date_parts = collect_state_values(valid_structured_state())

    return find_violations(
        text,
        quantities=quantities,
        date_parts=date_parts,
        device_words=config.device_words,
        control_words=config.control_words,
        number_tolerance=config.number_tolerance,
    )


def test_numbers_dates_and_times_from_the_state_pass() -> None:
    text = "Der Verbrauch lag etwa 311 % über dem üblichen Wert, am 15.12. um 11:00."

    assert _check(text) == ()


def test_numbers_and_dates_missing_in_the_state_are_found() -> None:
    violations = _check("Etwa 50 % mehr als sonst, zuletzt am 20.12.")

    assert [violation.kind for violation in violations] == ["number", "number"]


def test_device_and_control_words_are_found() -> None:
    violations = _check("Schalte die Waschmaschine aus.")

    assert {violation.kind for violation in violations} == {"device", "control"}
