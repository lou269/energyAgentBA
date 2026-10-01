# python -m pytest tests/unit/llm/test_llm_schema.py -v

from typing import Any, cast

import pytest

from src.llm.llm_schema import build_llm_output_json_schema, validate_llm_output

from tests.unit.llm._state_fixture import valid_llm_output


def test_valid_output_passes() -> None:
    validate_llm_output(valid_llm_output())


def test_missing_field_is_rejected() -> None:
    output = valid_llm_output()
    del output["uncertainty"]

    with pytest.raises(ValueError, match="missing required fields"):
        validate_llm_output(output)


def test_unexpected_field_is_rejected() -> None:
    output = valid_llm_output()
    output["confidence"] = 0.9

    with pytest.raises(ValueError, match="unexpected fields"):
        validate_llm_output(output)


def test_wrong_schema_version_is_rejected() -> None:
    output = valid_llm_output()
    output["schema_version"] = "2.0"

    with pytest.raises(ValueError):
        validate_llm_output(output)


def test_unsupported_classification_is_rejected() -> None:
    output = valid_llm_output()
    output["classification"] = "new_device"

    with pytest.raises(ValueError):
        validate_llm_output(output)


def test_empty_text_field_is_rejected() -> None:
    output = valid_llm_output()
    output["explanation"] = "   "

    with pytest.raises(ValueError):
        validate_llm_output(output)


def test_evidence_references_must_not_be_empty() -> None:
    output = valid_llm_output()
    output["evidence_references"] = []

    with pytest.raises(ValueError):
        validate_llm_output(output)


def test_evidence_reference_with_value_is_rejected() -> None:
    output = valid_llm_output()
    output["evidence_references"] = [{"path": "anomaly.level", "value": "unusual"}]

    with pytest.raises(ValueError, match="unexpected fields"):
        validate_llm_output(output)


@pytest.mark.parametrize("path", ["", "a..b"])
def test_evidence_path_syntax_is_rejected(path: str) -> None:
    output = valid_llm_output()
    output["evidence_references"] = [{"path": path}]

    with pytest.raises(ValueError):
        validate_llm_output(output)


def test_measurement_error_classification_is_accepted() -> None:
    output = valid_llm_output()
    output["classification"] = "measurement_error"
    output["evidence_references"] = [{"path": "observation.value_implausible"}]

    validate_llm_output(output)


def test_build_output_json_schema_sorts_and_deduplicates_paths() -> None:
    schema = cast(
        dict[str, Any], build_llm_output_json_schema(["b.path", "a.path", "a.path"])
    )

    path_schema = schema["properties"]["evidence_references"]["items"]["properties"][
        "path"
    ]
    assert path_schema["enum"] == ["a.path", "b.path"]
