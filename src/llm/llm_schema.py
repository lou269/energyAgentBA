from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from typing import Literal, TypedDict, get_args


SCHEMA_VERSION = "1.0"


Classification = Literal["normal", "absence", "peak", "unknown"]

CLASSIFICATIONS: frozenset[str] = frozenset(get_args(Classification))

OUTPUT_FIELDS = frozenset(
    {
        "schema_version",
        "classification",
        "explanation",
        "evidence_references",
        "user_recommendation",
        "uncertainty",
    }
)

EVIDENCE_REFERENCE_FIELDS = frozenset({"path", "value"})

EvidenceValue = str | int | float | bool | None


class EvidenceReference(TypedDict):
    path: str
    value: EvidenceValue


class LLMOutput(TypedDict):
    schema_version: str
    classification: Classification
    explanation: str
    evidence_references: list[EvidenceReference]
    user_recommendation: str
    uncertainty: str


def build_llm_output_json_schema(
    allowed_evidence_paths: Collection[str],
) -> dict[str, object]:
    paths = _normalize_allowed_evidence_paths(allowed_evidence_paths)

    return _build_output_schema(path_schema={"type": "string", "enum": paths})


def _build_output_schema(*, path_schema: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "classification": {"type": "string", "enum": sorted(CLASSIFICATIONS)},
            "explanation": {"type": "string", "minLength": 1},
            "evidence_references": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "path": path_schema,
                        "value": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "boolean"},
                                {"type": "null"},
                            ]
                        },
                    },
                    "required": ["path", "value"],
                    "additionalProperties": False,
                },
            },
            "user_recommendation": {"type": "string", "minLength": 1},
            "uncertainty": {"type": "string", "minLength": 1},
        },
        "required": [
            "schema_version",
            "classification",
            "explanation",
            "evidence_references",
            "user_recommendation",
            "uncertainty",
        ],
        "additionalProperties": False,
    }


def _normalize_allowed_evidence_paths(
    allowed_evidence_paths: Collection[str],
) -> list[str]:
    if isinstance(allowed_evidence_paths, (str, bytes)):
        raise TypeError("allowed_evidence_paths must be a collection of paths, not a single string.")

    normalized_paths: set[str] = set()

    for path in allowed_evidence_paths:
        _validate_evidence_path(path, "allowed evidence path")
        normalized_paths.add(path)

    if not normalized_paths:
        raise ValueError("allowed_evidence_paths must contain at least one scalar path.")

    return sorted(normalized_paths)


def validate_llm_output(output: object) -> None:
    if not isinstance(output, Mapping):
        raise TypeError("LLM output must be an object.")

    _validate_fields(output, OUTPUT_FIELDS, "LLM output")

    schema_version = output["schema_version"]
    if not isinstance(schema_version, str):
        raise TypeError("schema_version must be a string.")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}.")

    classification = output["classification"]
    if not isinstance(classification, str):
        raise TypeError("classification must be a string.")
    if classification not in CLASSIFICATIONS:
        raise ValueError("classification contains an unsupported value.")

    for field in ("explanation", "user_recommendation", "uncertainty"):
        _validate_non_empty_string(output[field], field)

    evidence_references = output["evidence_references"]

    if not isinstance(evidence_references, list):
        raise TypeError("evidence_references must be a list.")

    if not evidence_references:
        raise ValueError("evidence_references must contain at least one reference.")

    for index, reference in enumerate(evidence_references):
        name = f"evidence_references[{index}]"

        if not isinstance(reference, Mapping):
            raise TypeError(f"{name} must be an object.")

        _validate_fields(reference, EVIDENCE_REFERENCE_FIELDS, name)

        _validate_evidence_path(reference["path"], f"{name}.path")

        _validate_evidence_value(reference["value"], f"{name}.value")


def _validate_evidence_path(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    if not value:
        raise ValueError(f"{field_name} must not be empty.")

    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace.")

    if any(not part for part in value.split(".")):
        raise ValueError(f"{field_name} must be a valid dot-separated path.")

    return value


def _validate_evidence_value(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise TypeError(f"{field_name} must be a JSON scalar or null.")

    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite.")


def _validate_fields(
    value: Mapping[object, object], expected: frozenset[str], name: str
) -> None:
    missing = expected.difference(value)
    unexpected = set(value).difference(expected)

    if missing:
        fields = ", ".join(sorted(missing))
        raise ValueError(f"{name} is missing required fields: {fields}")

    if unexpected:
        fields = ", ".join(sorted(str(field) for field in unexpected))
        raise ValueError(f"{name} contains unexpected fields: {fields}")


def _validate_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")

    return value

