from collections.abc import Collection, Mapping
from typing import cast

from src.llm.llm_schema import (
    EvidenceReference,
    EvidenceValue,
    LLMOutput,
    RawLLMOutput,
    validate_llm_output,
)
from src.structured_state.structured_state_schema import StructuredState


EvidenceScalar = str | int | float | bool | None


ALLOWED_EVIDENCE_PATHS = frozenset(
    {
        "observation.value_implausible",
        "anomaly.level",
        "anomaly.direction",
        "anomaly.scale_scores.daily",
        "anomaly.scale_scores.weekday",
        "anomaly.scale_scores.weekly",
        "anomaly.scale_anomaly_streak_days.weekday",
        "anomaly.scale_anomaly_streak_days.weekly",
        "anomaly.scale_anomaly_streak_days.long_term",
        "anomaly.scale_deviation_pct.weekday",
        "anomaly.scale_deviation_pct.weekly",
        "anomaly.scale_deviation_pct.long_term",
        "anomaly.sustained_drift",
        "context.source_available",
    }
)

ALLOWED_EVENT_FIELDS = frozenset({"event_type", "start", "end"})


def _is_allowed_evidence_path(path: str) -> bool:
    if path in ALLOWED_EVIDENCE_PATHS:
        return True

    parts = path.split(".")

    return (
        len(parts) == 4
        and parts[0] == "context"
        and parts[1] == "events"
        and parts[2].isdigit()
        and parts[3] in ALLOWED_EVENT_FIELDS
    )


def collect_scalar_evidence_paths(state: StructuredState) -> tuple[str, ...]:
    paths: set[str] = set()
    _collect_scalar_paths(value=state, prefix="", paths=paths)

    if not paths:
        raise ValueError("Structured State does not contain any scalar evidence paths.")

    allowed_paths = tuple(
        sorted(path for path in paths if _is_allowed_evidence_path(path))
    )

    if not allowed_paths:
        raise ValueError("Structured State does not contain usable LLM evidence.")

    return allowed_paths


def validate_llm_output_against_state(
    output: RawLLMOutput,
    state: StructuredState,
    *,
    allowed_paths: Collection[str] | None = None,
) -> LLMOutput:
    # value kommt nie vom Modell, sondern wird hier aus dem State nachgeschlagen
    allowed_paths = frozenset(
        allowed_paths
        if allowed_paths is not None
        else collect_scalar_evidence_paths(state)
    )
    validate_llm_output(output)

    referenced_paths: set[str] = set()
    resolved_references: list[EvidenceReference] = []

    for index, reference in enumerate(output["evidence_references"]):
        path = reference["path"]
        reference_name = f"evidence_references[{index}]"

        if path in referenced_paths:
            raise ValueError(
                f"{reference_name}.path contains a duplicate evidence path: {path!r}."
            )

        referenced_paths.add(path)

        if path not in allowed_paths:
            raise ValueError(
                f"{reference_name}.path is not an existing scalar Structured-State path: {path!r}."
            )

        state_value = _resolve_path(state, path)

        if isinstance(state_value, (Mapping, list)):
            raise ValueError(
                f"{reference_name}.path must reference a scalar value, not an object or list: {path!r}."
            )

        if not _is_json_scalar(state_value):
            raise TypeError(
                f"Structured-State value at {path!r} is not a supported JSON scalar."
            )

        resolved_references.append(
            {"path": path, "value": cast(EvidenceValue, state_value)}
        )

    return {
        "schema_version": output["schema_version"],
        "classification": output["classification"],
        "explanation": output["explanation"],
        "evidence_references": resolved_references,
        "user_recommendation": output["user_recommendation"],
        "uncertainty": output["uncertainty"],
    }


def _collect_scalar_paths(*, value: object, prefix: str, paths: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise TypeError("Structured State contains a non-string object key.")

            nested_prefix = f"{prefix}.{key}" if prefix else key

            _collect_scalar_paths(value=nested_value, prefix=nested_prefix, paths=paths)

        return

    if isinstance(value, list):
        for index, nested_value in enumerate(value):
            nested_prefix = f"{prefix}.{index}" if prefix else str(index)

            _collect_scalar_paths(value=nested_value, prefix=nested_prefix, paths=paths)

        return

    if not prefix:
        raise ValueError("Structured State root must be an object.")

    if not _is_json_scalar(value):
        raise TypeError(
            f"Structured-State value at {prefix!r} is not a supported JSON scalar."
        )

    paths.add(prefix)


def _resolve_path(state: StructuredState, path: str) -> object:
    parts = path.split(".")

    if any(not part for part in parts):
        raise ValueError(f"Invalid evidence path: {path!r}.")

    current: object = state

    for part in parts:
        if isinstance(current, Mapping):
            if part not in current:
                raise ValueError(
                    f"Evidence path does not exist in Structured State: {path!r}."
                )

            current = current[part]
            continue

        if isinstance(current, list):
            if not part.isdigit():
                raise ValueError(
                    f"Evidence path requires a non-negative list index: {path!r}."
                )

            index = int(part)

            if index >= len(current):
                raise ValueError(
                    f"Evidence path contains an invalid list index: {path!r}."
                )

            current = current[index]
            continue

        raise ValueError(
            f"Evidence path continues after reaching a scalar Structured-State value: {path!r}."
        )

    return current


def _is_json_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))
