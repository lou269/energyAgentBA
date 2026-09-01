from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import platform
from typing import Any
from uuid import uuid4

from src.pipeline.provenance import (
    build_source_fingerprint,
    file_sha256,
    git_output,
    json_sha256,
)


VALID_OUTPUT_STATUSES = {"generated", "reused"}


def build_analysis_manifest(
    project_root: Path,
    ingestion_run_id: str,
    dataset_path: Path,
    config_values: dict[str, Any],
    source_paths: tuple[Path, ...],
    output_status: Mapping[Path, str],
    overwrite: Mapping[str, bool],
) -> dict[str, Any]:
    if not output_status:
        raise ValueError("No analysis outputs provided.")

    outputs: dict[str, dict[str, Any]] = {}

    for output_path, status in output_status.items():
        if status not in VALID_OUTPUT_STATUSES:
            raise ValueError(
                f"Invalid output status for {output_path}: {status}"
            )

        if not output_path.is_file():
            raise FileNotFoundError(
                f"Analysis output does not exist: {output_path}"
            )

        relative_path = str(
            output_path.relative_to(project_root)
        )

        outputs[relative_path] = {
            "path": str(output_path),
            "size_bytes": output_path.stat().st_size,
            "sha256": file_sha256(output_path),
            "status": status,
        }

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
        "code_version": {
            "source_fingerprint": build_source_fingerprint(
                project_root=project_root,
                source_paths=source_paths,
            ),
            "git_commit": git_output(
                project_root,
                "rev-parse",
                "HEAD",
            ),
            "git_dirty": bool(
                git_output(
                    project_root,
                    "status",
                    "--porcelain",
                )
            ),
        },
        "runtime_version": {
            "python": platform.python_version(),
            "python_implementation": (
                platform.python_implementation()
            ),
            "platform": platform.platform(),
            "pandas": version("pandas"),
            "nilmtk": version("nilmtk"),
        },
        "run_parameters": {
            "overwrite": dict(overwrite),
        },
        "outputs": outputs,
    }

    return manifest