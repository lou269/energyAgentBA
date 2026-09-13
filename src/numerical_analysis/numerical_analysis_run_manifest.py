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


def build_numerical_analysis_run_manifest(
    *,
    project_root: Path,
    run_id: str,
    candidate_id: str,
    config_values: Mapping[str, Any],
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

    config = dict(config_values)

    return {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "config": {"values": config, "sha256": json_sha256(config)},
        "inputs": inputs,
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference(project_root, project_root / "environment-forecasting.yml"),
        "runtime_seconds": runtime_seconds,
        "outputs": outputs,
    }
