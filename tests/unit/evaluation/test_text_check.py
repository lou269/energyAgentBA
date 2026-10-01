# python -m pytest tests/unit/evaluation/test_text_check.py -v

from src.config.config_forecasting import TextCheckConfig
from src.evaluation.text_check import (
    TextViolation,
    collect_state_values,
    find_device_mentions,
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
        control_words=config.control_words,
        number_tolerance=config.number_tolerance,
        prompt_numbers=(7.0, 30.0),
    )


def test_state_values_pass() -> None:
    text = "Der Verbrauch lag etwa 311 % über dem üblichen Wert, am 15.12. um 00:00."

    assert _check(text) == ()


def test_foreign_numbers_found() -> None:
    violations = _check("Etwa 50 % mehr als sonst, zuletzt am 20.12.")

    assert [violation.kind for violation in violations] == ["number", "number"]


def test_control_vs_device_words() -> None:
    text = "Schalte die Waschmaschine aus."

    assert [violation.kind for violation in _check(text)] == ["control"]
    assert find_device_mentions(text, device_words=TextCheckConfig().device_words) == (
        "waschmaschine",
    )


def test_month_dates_and_windows() -> None:
    text = (
        "Abwesenheit vom 15. bis 22. Dezember, über die letzten 30 Tage 14 % weniger."
    )

    assert [violation.found for violation in _check(text)] == ["14"]


def test_word_inside_word() -> None:
    text = "Geräte könnten ausgeschaltet worden sein."

    assert _check(text) == ()
