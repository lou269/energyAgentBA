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
    config_values: Mapping[str, Mapping[str, Any]],
    coldstart_days: int,
    decision_time_count: int,
    decision_time_start: str | None,
    decision_time_end: str | None,
    row_count: int,
    llm_failure_count: int,
    llm_failures_file: Path | None,
    output_paths: Mapping[str, Path],
    runtime_seconds: float,
) -> dict[str, Any]:
    outputs = {
        name: build_file_metadata(project_root, path)
        for name, path in output_paths.items()
    }

    return {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "configs": {
            "labels": list(config_values),
            "values": config_values,
            "sha256": json_sha256(config_values),
        },
        "scenario": {
            "coldstart_days": coldstart_days,
            "decision_time_count": decision_time_count,
            "decision_time_start": decision_time_start,
            "decision_time_end": decision_time_end,
        },
        "row_count": row_count,
        "llm_failures": {
            "count": llm_failure_count,
            "file": _relative_path(project_root, llm_failures_file),
        },
        "runtime_seconds": runtime_seconds,
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference(project_root, project_root / "environment-forecasting.yml"),
        "outputs": outputs,
    }
