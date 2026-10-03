# python -m pytest tests/unit/llm/test_gate.py -v

from src.llm.gate import gate_classification
from src.structured_state.structured_state_schema import StructuredState

from tests.unit.llm._state_fixture import valid_structured_state


def _state(
    *,
    level: str | None,
    sustained_scales: list[str] | None = None,
    value_implausible: bool = False,
) -> StructuredState:
    state = valid_structured_state()
    state["anomaly"]["level"] = level  # type: ignore[typeddict-item]
    state["anomaly"]["sustained_scales"] = sustained_scales or []  # type: ignore[typeddict-item]
    state["observation"]["value_implausible"] = value_implausible
    return state


def test_closed_gate_decides_without_rule_or_llm() -> None:
    assert gate_classification(_state(level="normal")) == "normal"
    assert gate_classification(_state(level=None)) == "unknown"


def test_unusual_day_opens_the_gate() -> None:
    assert gate_classification(_state(level="unusual")) is None


def test_one_sustained_scale_opens_the_gate_on_an_unremarkable_or_unscored_day() -> (
    None
):
    assert (
        gate_classification(_state(level="normal", sustained_scales=["weekly"])) is None
    )
    assert gate_classification(_state(level=None, sustained_scales=["weekly"])) is None


def test_implausible_day_opens_the_gate_before_the_missing_level_check() -> None:
    assert gate_classification(_state(level=None, value_implausible=True)) is None
    assert gate_classification(_state(level="normal", value_implausible=True)) is None
