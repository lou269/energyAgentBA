from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path
import platform
from typing import Any
from uuid import uuid4

from src.pipeline.provenance import (
    file_sha256,
    git_output,
    json_sha256,
)


def build_ingestion_manifest(
    project_root: Path,
    archive_path: Path,
    dataset_path: Path,
    dataset_release: str,
    dataset_doi: str,
    config_values: dict[str, Any],
    overwrite: bool,
) -> dict[str, Any]:
    package_versions: dict[str, str] = {}

    for distribution in distributions():
        package_name = distribution.metadata["Name"]
        if package_name:
            package_versions[package_name] = distribution.version

    manifest = {
        "run_id": str(uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_version": {
            "release": dataset_release,
            "doi": dataset_doi,
            "archive": {
                "path": str(archive_path),
                "size_bytes": archive_path.stat().st_size,
                "sha256": file_sha256(archive_path),
            },
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
            "packages": dict(sorted(package_versions.items())),
        },
        "run_parameters": {
            "overwrite": overwrite,
        },
    }

    return manifest