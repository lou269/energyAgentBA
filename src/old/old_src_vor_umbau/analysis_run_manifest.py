from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.pipeline.provenance import (
    build_code_version,
    build_environment_reference,
    build_file_metadata,
    file_sha256,
    json_sha256,
)


def build_analysis_manifest(
    project_root: Path,
    ingestion_run_id: str,
    dataset_path: Path,
    config_values: dict[str, Any],
    output_paths: Iterable[Path],
) -> dict[str, Any]:
    outputs = {
        str(output_path.relative_to(project_root)): build_file_metadata(project_root, output_path)
        for output_path in output_paths
    }

    if not outputs:
        raise ValueError("No analysis outputs provided.")

    manifest = {
        "run_id": str(uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ingestion": {
            "run_id": ingestion_run_id,
        },
        "input": {
            "hdf5": {
                "path": str(dataset_path),
                "size_bytes": dataset_path.stat().st_size,
                "sha256": file_sha256(dataset_path),
            },
        },
        "config": {
            "values": config_values,
            "sha256": json_sha256(config_values),
        },
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference(project_root, project_root / "environment-nilmtk.yml"),
        "outputs": outputs,
    }

    return manifest
