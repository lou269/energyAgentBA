from __future__ import annotations

from collections.abc import Collection, Mapping

from src.llm.llm_schema import LLMOutput, validate_llm_output
from src.structured_state.structured_state_schema import StructuredState, validate_structured_state


EvidenceScalar = str | int | float | bool | None


ALLOWED_EVIDENCE_PATHS = frozenset(
    {
        "observation.current_power_w",
        "observation.value_implausible",
        "analysis.short_term_mean_w",
        "analysis.daily_expected_w",
        "analysis.weekly_expected_w",
        "analysis.long_term_mean_w",
        "analysis.trend_slope_w_per_hour",
        "analysis.trend_change",
        "analysis.trend",
        "anomaly.score",
        "anomaly.level",
        "anomaly.direction",
        "anomaly.dominant_scale",
        "anomaly.scale_scores.short_term",
        "anomaly.scale_scores.daily",
        "anomaly.scale_scores.weekly",
        "anomaly.scale_scores.long_term",
        "anomaly.scale_elevated_hours.short_term",
        "anomaly.scale_elevated_hours.daily",
        "anomaly.scale_elevated_hours.weekly",
        "anomaly.scale_elevated_hours.long_term",
        "forecast.summary.mean_w",
        "forecast.summary.peak_w",
        "forecast.summary.peak_timestamp",
        "forecast.summary.mean_interval_width_w",
        "context.source_available",
    }
)

ALLOWED_EVENT_FIELDS = frozenset({"event_type", "start", "end"})


def _is_allowed_evidence_path(
    path: str
) -> bool:
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


def collect_scalar_evidence_paths(
    state: StructuredState
) -> tuple[str, ...]:
    validate_structured_state(state)

    paths: set[str] = set()
    _collect_scalar_paths(value=state, prefix="", paths=paths)

    if not paths:
        raise ValueError("Structured State does not contain any scalar evidence paths.")

    allowed_paths = tuple(sorted(path for path in paths if _is_allowed_evidence_path(path)))

    if not allowed_paths:
        raise ValueError("Structured State does not contain usable LLM evidence.")

    return allowed_paths


def validate_llm_output_against_state(
    output: LLMOutput,
    state: StructuredState,
    *,
    allowed_paths: Collection[str] | None = None,
) -> None:
    allowed_paths = frozenset(allowed_paths if allowed_paths is not None else collect_scalar_evidence_paths(state))
    validate_llm_output(output)

    referenced_paths: set[str] = set()

    for index, reference in enumerate(output["evidence_references"]):
        path = reference["path"]
        referenced_value = reference["value"]
        reference_name = f"evidence_references[{index}]"

        if path in referenced_paths:
            raise ValueError(f"{reference_name}.path contains a duplicate evidence path: {path!r}.")

        referenced_paths.add(path)

        if path not in allowed_paths:
            raise ValueError(f"{reference_name}.path is not an existing scalar Structured-State path: {path!r}.")

        state_value = _resolve_path(state, path)

        if isinstance(state_value, (Mapping, list)):
            raise ValueError(f"{reference_name}.path must reference a scalar value, not an object or list: {path!r}.")

        if not _is_json_scalar(state_value):
            raise TypeError(f"Structured-State value at {path!r} is not a supported JSON scalar.")

        if type(referenced_value) is not type(state_value):
            raise ValueError(
                f"{reference_name}.value has the wrong JSON type for {path!r}: expected {type(state_value).__name__}, got {type(referenced_value).__name__}."
            )

        if referenced_value != state_value:
            raise ValueError(
                f"{reference_name}.value does not match the Structured State for {path!r}: expected {state_value!r}, got {referenced_value!r}."
            )


def _collect_scalar_paths(
    *, 
    value: object, 
    prefix: str, 
    paths: set[str]
) -> None:
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
        raise TypeError(f"Structured-State value at {prefix!r} is not a supported JSON scalar.")

    paths.add(prefix)



def _resolve_path(
    state: StructuredState, 
    path: str
) -> object:
    parts = path.split(".")

    if any(not part for part in parts):
        raise ValueError(f"Invalid evidence path: {path!r}.")

    current: object = state


    for part in parts:
        if isinstance(current, Mapping):
            if part not in current:
                raise ValueError(f"Evidence path does not exist in Structured State: {path!r}.")

            current = current[part]
            continue

        if isinstance(current, list):
            if not part.isdigit():
                raise ValueError(f"Evidence path requires a non-negative list index: {path!r}.")

            index = int(part)

            if index >= len(current):
                raise ValueError(f"Evidence path contains an invalid list index: {path!r}.")

            current = current[index]
            continue

        raise ValueError(f"Evidence path continues after reaching a scalar Structured-State value: {path!r}.")

    return current



def _is_json_scalar(
    value: object
) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))

