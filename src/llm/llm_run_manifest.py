from __future__ import annotations

import math
import platform
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from src.pipeline.provenance import (
    build_source_fingerprint,
    file_sha256,
    git_output,
    json_sha256,
)


LLMRunStatus = Literal["valid", "invalid_output", "request_failed"]

LLM_RUN_STATUSES = frozenset({"valid", "invalid_output", "request_failed"})

REQUIRED_INPUTS = frozenset({"structured_state", "prompt"})

REQUIRED_OUTPUTS = frozenset({"structured_state", "attempts"})


def build_llm_run_manifest(
    *,
    project_root: Path,
    run_id: str,
    status: LLMRunStatus,
    decision_time: str,
    forecast_run_id: str,
    config_values: Mapping[str, Any],
    model_metadata: Mapping[str, Any],
    source_paths: tuple[Path, ...],
    input_paths: Mapping[str, Path],
    output_paths: Mapping[str, Path],
    attempt_records: tuple[Mapping[str, Any], ...],
    runtime_seconds: float,
    error: Exception | None,
) -> dict[str, Any]:
    _validate_non_empty_string(run_id, "run_id")
    _validate_non_empty_string(decision_time, "decision_time")
    _validate_non_empty_string(forecast_run_id, "forecast_run_id")

    if status not in LLM_RUN_STATUSES:
        raise ValueError(f"Unsupported LLM run status: {status!r}.")

    if (
        isinstance(runtime_seconds, bool)
        or not isinstance(runtime_seconds, (int, float))
        or not math.isfinite(float(runtime_seconds))
        or runtime_seconds < 0
    ):
        raise ValueError("runtime_seconds must be a finite non-negative number.")

    _validate_required_paths(input_paths, REQUIRED_INPUTS, "input")
    _validate_required_paths(output_paths, REQUIRED_OUTPUTS, "output")

    if status == "valid":
        if "llm_output" not in output_paths:
            raise ValueError("A valid LLM run must provide an llm_output artifact.")

        if error is not None:
            raise ValueError("A valid LLM run must not contain an error.")
    elif error is None:
        raise ValueError("A failed LLM run must contain an error.")

    attempts = _build_attempt_summaries(attempt_records)
    valid_attempts = [
        attempt["attempt_number"] for attempt in attempts if attempt["valid"]
    ]

    if status == "valid" and len(valid_attempts) != 1:
        raise ValueError("A valid LLM run must contain exactly one valid attempt.")

    if status != "valid" and valid_attempts:
        raise ValueError("A failed LLM run must not contain a valid attempt.")

    config = dict(config_values)
    model = dict(model_metadata)

    model_name = model.get("name")
    _validate_non_empty_string(model_name, "model_metadata.name")

    inputs = {
        name: _build_file_metadata(project_root, path)
        for name, path in input_paths.items()
    }
    outputs = {
        name: _build_file_metadata(project_root, path)
        for name, path in output_paths.items()
    }

    return {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision_time": decision_time,
        "forecast": {"run_id": forecast_run_id},
        "model": model,
        "config": {"values": config, "sha256": json_sha256(config)},
        "inputs": inputs,
        "inference": {
            "attempt_count": len(attempts),
            "first_attempt_valid": (bool(attempts) and bool(attempts[0]["valid"])),
            "retry_used": len(attempts) > 1,
            "valid_attempt": (valid_attempts[0] if valid_attempts else None),
            "attempts": attempts,
            "runtime_seconds": float(runtime_seconds),
            "timing_scope": "model_metadata_and_inference",
        },
        "error": (
            None
            if error is None
            else {"type": type(error).__name__, "message": str(error)}
        ),
        "code_version": {
            "source_fingerprint": build_source_fingerprint(
                project_root=project_root, source_paths=source_paths
            ),
            "git_commit": git_output(project_root, "rev-parse", "HEAD"),
            "git_dirty": bool(git_output(project_root, "status", "--porcelain")),
        },
        "runtime_version": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "ollama_client": _package_version("ollama"),
            "pandas": _package_version("pandas"),
        },
        "outputs": outputs,
    }


def _build_attempt_summaries(
    attempt_records: tuple[Mapping[str, Any], ...],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    expected_numbers = list(range(1, len(attempt_records) + 1))
    actual_numbers: list[int] = []

    for index, record in enumerate(attempt_records):
        name = f"attempt_records[{index}]"

        attempt_number = record.get("attempt_number")
        valid = record.get("valid")
        validation_error = record.get("validation_error")
        generation_seconds = record.get("generation_seconds")
        raw_content = record.get("raw_content")

        if (
            isinstance(attempt_number, bool)
            or not isinstance(attempt_number, int)
            or attempt_number < 1
        ):
            raise ValueError(f"{name}.attempt_number must be a positive integer.")

        if not isinstance(valid, bool):
            raise TypeError(f"{name}.valid must be a boolean.")

        if not isinstance(raw_content, str):
            raise TypeError(f"{name}.raw_content must be a string.")

        if (
            isinstance(generation_seconds, bool)
            or not isinstance(generation_seconds, (int, float))
            or not math.isfinite(float(generation_seconds))
            or generation_seconds < 0
        ):
            raise ValueError(f"{name}.generation_seconds must be a finite non-negative number.")
        
        if valid:
            if validation_error is not None:
                raise ValueError(f"{name} is valid and must not contain a validation error.")
            
        elif not isinstance(validation_error, str) or not validation_error.strip():
            raise ValueError(f"{name} is invalid and must contain a validation error.")

        actual_numbers.append(attempt_number)

        summaries.append(
            {
                "attempt_number": attempt_number,
                "valid": valid,
                "validation_error": validation_error,
                "generation_seconds": float(generation_seconds),
                "raw_content_sha256": sha256(raw_content.encode("utf-8")).hexdigest(),
            }
        )

    if actual_numbers != expected_numbers:
        raise ValueError("Attempt numbers must be consecutive and start at 1.")

    valid_indices = [
        index for index, summary in enumerate(summaries) if summary["valid"]
    ]

    if len(valid_indices) > 1:
        raise ValueError("Attempt records must contain at most one valid attempt.")

    if valid_indices and valid_indices[0] != len(summaries) - 1:
        raise ValueError("A valid attempt must be the final attempt.")

    return summaries


def _validate_required_paths(
    paths: Mapping[str, Path], required: frozenset[str], name: str
) -> None:
    missing = required.difference(paths)

    if missing:
        raise ValueError(f"Missing required {name} paths: " + ", ".join(sorted(missing)))



def _build_file_metadata(project_root: Path, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Manifest file does not exist: {path}")

    try:
        relative_path = str(path.relative_to(project_root))
    except ValueError:
        relative_path = str(path)

    return {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def _validate_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")

    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace.")

    return value


def _package_version(package_name: str) -> str | None:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None