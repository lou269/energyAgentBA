from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipeline.provenance import (
    build_code_version,
    build_environment_reference,
    build_file_metadata,
    json_sha256,
)


def build_structured_state_run_manifest(
    *,
    project_root: Path,
    run_id: str,
    decision_time: str,
    model_id: str,
    split: str,
    forecast_run_directory: str,
    forecast_run_number: int,
    analysis_run_directory: str,
    analysis_run_number: int,
    calendar_source: str,
    calendar_source_available: bool,
    calendar_retrieved_at: str,
    calendar_window_start: str,
    calendar_window_end: str,
    input_paths: Mapping[str, Path],
    output_paths: Mapping[str, Path],
    runtime_seconds: float,
) -> dict[str, Any]:
    inputs = {
        name: build_file_metadata(project_root, path)
        for name, path in input_paths.items()
    }
    outputs = {
        name: build_file_metadata(project_root, path)
        for name, path in output_paths.items()
    }

    config_values = {
        "decision_time": decision_time,
        "model_id": model_id,
        "split": split,
        "forecast_run_number": forecast_run_number,
        "analysis_run_number": analysis_run_number,
        "calendar_source": calendar_source,
        "calendar_source_available": calendar_source_available,
        "calendar_retrieved_at": calendar_retrieved_at,
        "calendar_window_start": calendar_window_start,
        "calendar_window_end": calendar_window_end,
    }

    return {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision_time": decision_time,
        "forecast": {
            "directory": forecast_run_directory,
            "run_number": forecast_run_number,
        },
        "numerical_analysis": {
            "directory": analysis_run_directory,
            "run_number": analysis_run_number,
        },
        "config": {
            "values": config_values,
            "sha256": json_sha256(config_values),
        },
        "inputs": inputs,
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference(project_root, project_root / "environment-forecasting.yml"),
        "runtime_seconds": runtime_seconds,
        "outputs": outputs,
    }
