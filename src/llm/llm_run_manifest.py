from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from src.pipeline.provenance import (
    build_code_version,
    build_environment_reference,
    build_file_metadata,
    json_sha256,
)


LLMRunStatus = Literal["valid", "invalid_output", "request_failed"]


def build_llm_run_manifest(
    *,
    project_root: Path,
    run_id: str,
    status: LLMRunStatus,
    decision_time: str,
    forecast_run_id: str,
    config_values: Mapping[str, Any],
    model_metadata: Mapping[str, Any],
    input_paths: Mapping[str, Path],
    output_paths: Mapping[str, Path],
    attempt_records: tuple[Mapping[str, Any], ...],
    runtime_seconds: float,
    error: Exception | None,
) -> dict[str, Any]:
    attempts = [
        {
            "attempt_number": record["attempt_number"],
            "valid": record["valid"],
            "validation_error": record["validation_error"],
            "generation_seconds": float(record["generation_seconds"]),
            "raw_content_sha256": sha256(record["raw_content"].encode("utf-8")).hexdigest(),
        }
        for record in attempt_records
    ]
    valid_attempts = [
        attempt["attempt_number"] for attempt in attempts if attempt["valid"]
    ]

    inputs = {
        name: build_file_metadata(project_root, path)
        for name, path in input_paths.items()
    }
    outputs = {
        name: build_file_metadata(project_root, path)
        for name, path in output_paths.items()
    }

    config = dict(config_values)
    model = dict(model_metadata)

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
        },
        "error": (
            None
            if error is None
            else {"type": type(error).__name__, "message": str(error)}
        ),
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference(project_root, project_root / "environment-forecasting.yml"),
        "outputs": outputs,
    }
