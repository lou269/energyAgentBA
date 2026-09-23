# python -m pytest tests/unit/llm/test_gate.py -v

from src.llm.gate import gate_classification
from src.structured_state.structured_state_schema import StructuredState

from tests.unit.llm._state_fixture import valid_structured_state



def _state(*, level: str | None, sustained_drift: bool = False, value_implausible: bool = False) -> StructuredState:
    state = valid_structured_state()
    state["anomaly"]["level"] = level  # type: ignore[typeddict-item]
    state["anomaly"]["sustained_drift"] = sustained_drift
    state["observation"]["value_implausible"] = value_implausible
    return state


def test_closed_gate_decides_without_rule_or_llm() -> None:
    assert gate_classification(_state(level="normal")) == "normal"
    assert gate_classification(_state(level=None)) == "unknown"
    assert gate_classification(_state(level="unusual", value_implausible=True)) == "measurement_error"


def test_unusual_day_opens_the_gate() -> None:
    assert gate_classification(_state(level="unusual")) is None


def test_drift_opens_the_gate_on_an_unremarkable_or_unscored_day() -> None:
    assert gate_classification(_state(level="normal", sustained_drift=True)) is None
    assert gate_classification(_state(level=None, sustained_drift=True)) is None


def test_measurement_error_wins_over_drift() -> None:
    assert gate_classification(_state(level="normal", sustained_drift=True, value_implausible=True)) == "measurement_error"

