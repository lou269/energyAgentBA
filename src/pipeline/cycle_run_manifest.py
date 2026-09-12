from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pipeline.daily_cycle import CycleConfig
from src.pipeline.provenance import (
    build_code_version,
    build_environment_reference,
    build_file_metadata,
    json_sha256,
)


def _relative_path(project_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None

    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def build_cycle_run_manifest(
    *,
    project_root: Path,
    run_id: str,
    configs: Mapping[str, CycleConfig],
    coldstart_hours: int,
    decision_time_count: int,
    decision_time_start: str | None,
    decision_time_end: str | None,
    row_count: int,
    llm_failure_count: int,
    llm_failures_directory: Path | None,
    output_paths: Mapping[str, Path],
    runtime_seconds: float,
) -> dict[str, Any]:
    config_values = {label: asdict(config) for label, config in configs.items()}
    outputs = {
        name: build_file_metadata(project_root, path)
        for name, path in output_paths.items()
    }

    return {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "configs": {
            "labels": list(configs),
            "values": config_values,
            "sha256": json_sha256(config_values),
        },
        "scenario": {
            "coldstart_hours": coldstart_hours,
            "decision_time_count": decision_time_count,
            "decision_time_start": decision_time_start,
            "decision_time_end": decision_time_end,
        },
        "row_count": row_count,
        "llm_failures": {
            "count": llm_failure_count,
            "directory": _relative_path(project_root, llm_failures_directory),
        },
        "runtime_seconds": runtime_seconds,
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference(project_root, project_root / "environment-forecasting.yml"),
        "outputs": outputs,
    }
