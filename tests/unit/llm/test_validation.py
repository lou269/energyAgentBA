# python -m pytest tests/unit/llm/test_validation.py -v
from typing import cast

import pytest

from src.llm.llm_schema import LLMOutput
from src.llm.validation import ALLOWED_EVIDENCE_PATHS, collect_scalar_evidence_paths, validate_llm_output_against_state
from tests.unit.llm._state_fixture import valid_llm_output, valid_structured_state


def test_valid_output_is_accepted() -> None:
    validate_llm_output_against_state(cast(LLMOutput, valid_llm_output()), valid_structured_state())


def test_path_outside_allowlist_is_rejected_even_though_it_exists_in_state() -> None:
    state = valid_structured_state()
    assert "forecast.run_id" not in ALLOWED_EVIDENCE_PATHS
    assert state["forecast"]["run_id"] == "validation_003"

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "forecast.run_id", "value": "validation_003"}]

    with pytest.raises(ValueError, match="not an existing scalar Structured-State path"):
        validate_llm_output_against_state(cast(LLMOutput, output), state)


def test_rounded_value_is_rejected() -> None:
    state = valid_structured_state()
    daily_expected_w = state["analysis"]["daily_expected_w"]
    assert daily_expected_w is not None

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "analysis.daily_expected_w", "value": round(daily_expected_w, 2)}]

    with pytest.raises(ValueError, match="does not match the Structured State"):
        validate_llm_output_against_state(cast(LLMOutput, output), state)


def test_bool_referenced_as_int_is_rejected() -> None:
    state = valid_structured_state()
    assert state["context"]["source_available"] is True

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.source_available", "value": 1}]

    with pytest.raises(ValueError, match="wrong JSON type"):
        validate_llm_output_against_state(cast(LLMOutput, output), state)


def test_bool_referenced_as_bool_is_accepted() -> None:
    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.source_available", "value": True}]

    validate_llm_output_against_state(cast(LLMOutput, output), valid_structured_state())


def test_duplicate_evidence_path_is_rejected() -> None:
    output = valid_llm_output()
    output["evidence_references"] = [
        {"path": "observation.current_power_w", "value": 1319.8837},
        {"path": "observation.current_power_w", "value": 1319.8837},
    ]

    with pytest.raises(ValueError, match="duplicate evidence path"):
        validate_llm_output_against_state(cast(LLMOutput, output), valid_structured_state())


def test_event_id_is_not_an_allowed_evidence_path() -> None:
    state = valid_structured_state()
    event_id = state["context"]["events"][0]["event_id"]

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.events.0.event_id", "value": event_id}]

    with pytest.raises(ValueError, match="not an existing scalar Structured-State path"):
        validate_llm_output_against_state(cast(LLMOutput, output), state)


def test_event_type_is_an_allowed_evidence_path() -> None:
    state = valid_structured_state()
    event_type = state["context"]["events"][0]["event_type"]

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.events.0.event_type", "value": event_type}]

    validate_llm_output_against_state(cast(LLMOutput, output), state)


def test_value_implausible_is_an_allowed_evidence_path() -> None:
    assert "observation.value_implausible" in ALLOWED_EVIDENCE_PATHS

    paths = collect_scalar_evidence_paths(valid_structured_state())
    assert "observation.value_implausible" in paths


def test_measurement_error_grounded_by_value_implausible() -> None:
    state = valid_structured_state()
    state["observation"]["value_implausible"] = True

    output = valid_llm_output()
    output["classification"] = "measurement_error"
    output["evidence_references"] = [{"path": "observation.value_implausible", "value": True}]

    validate_llm_output_against_state(cast(LLMOutput, output), state)


def test_collect_scalar_evidence_paths_matches_static_allowlist() -> None:
    paths = set(collect_scalar_evidence_paths(valid_structured_state()))

    assert paths <= ALLOWED_EVIDENCE_PATHS | {
        "context.events.0.event_type",
        "context.events.0.start",
        "context.events.0.end",
    }
    assert "observation.current_power_w" in paths
    assert "forecast.run_id" not in paths
    assert "context.events.0.event_id" not in paths