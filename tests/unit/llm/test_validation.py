# python -m pytest tests/unit/llm/test_validation.py -v
from typing import cast

import pytest

from src.llm.llm_schema import RawLLMOutput
from src.llm.validation import (
    ALLOWED_EVIDENCE_PATHS,
    collect_scalar_evidence_paths,
    validate_llm_output_against_state,
)
from tests.unit.llm._state_fixture import valid_llm_output, valid_structured_state


def test_valid_output_is_accepted() -> None:
    validate_llm_output_against_state(
        cast(RawLLMOutput, valid_llm_output()), valid_structured_state()
    )


def test_path_outside_allowlist_is_rejected_even_though_it_exists_in_state() -> None:
    state = valid_structured_state()
    assert "context.source" not in ALLOWED_EVIDENCE_PATHS
    assert state["context"]["source"] == "simulated_calendar"

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.source"}]

    with pytest.raises(
        ValueError, match="not an existing scalar Structured-State path"
    ):
        validate_llm_output_against_state(cast(RawLLMOutput, output), state)


def test_value_is_resolved_at_full_precision() -> None:
    state = valid_structured_state()
    weekday_deviation_pct = state["anomaly"]["scale_deviation_pct"]["weekday"]
    assert weekday_deviation_pct is not None

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "anomaly.scale_deviation_pct.weekday"}]

    resolved = validate_llm_output_against_state(cast(RawLLMOutput, output), state)

    assert resolved["evidence_references"][0] == {
        "path": "anomaly.scale_deviation_pct.weekday",
        "value": weekday_deviation_pct,
    }


def test_bool_value_is_resolved_with_correct_type() -> None:
    state = valid_structured_state()
    assert state["context"]["source_available"] is True

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.source_available"}]

    resolved = validate_llm_output_against_state(cast(RawLLMOutput, output), state)

    value = resolved["evidence_references"][0]["value"]
    assert value is True
    assert type(value) is bool


def test_duplicate_evidence_path_is_rejected() -> None:
    output = valid_llm_output()
    output["evidence_references"] = [
        {"path": "anomaly.level"},
        {"path": "anomaly.level"},
    ]

    with pytest.raises(ValueError, match="duplicate evidence path"):
        validate_llm_output_against_state(
            cast(RawLLMOutput, output), valid_structured_state()
        )


def test_event_id_is_not_an_allowed_evidence_path() -> None:
    state = valid_structured_state()

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.events.0.event_id"}]

    with pytest.raises(
        ValueError, match="not an existing scalar Structured-State path"
    ):
        validate_llm_output_against_state(cast(RawLLMOutput, output), state)


def test_event_title_is_an_allowed_evidence_path() -> None:
    state = valid_structured_state()

    output = valid_llm_output()
    output["evidence_references"] = [{"path": "context.events.0.title"}]

    validate_llm_output_against_state(cast(RawLLMOutput, output), state)


def test_value_implausible_is_an_allowed_evidence_path() -> None:
    assert "observation.value_implausible" in ALLOWED_EVIDENCE_PATHS

    paths = collect_scalar_evidence_paths(valid_structured_state())
    assert "observation.value_implausible" in paths


def test_measurement_error_grounded_by_value_implausible() -> None:
    state = valid_structured_state()
    state["observation"]["value_implausible"] = True

    output = valid_llm_output()
    output["classification"] = "measurement_error"
    output["evidence_references"] = [{"path": "observation.value_implausible"}]

    validate_llm_output_against_state(cast(RawLLMOutput, output), state)


def test_collect_scalar_evidence_paths_matches_static_allowlist() -> None:
    paths = set(collect_scalar_evidence_paths(valid_structured_state()))

    assert paths <= ALLOWED_EVIDENCE_PATHS | {
        "context.events.0.title",
        "context.events.0.start",
        "context.events.0.end",
    }
    assert "anomaly.scale_deviation_pct.weekday" in paths
    assert "forecast.run_id" not in paths
    assert "context.events.0.event_id" not in paths
