from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.pipeline.provenance import build_code_version, build_environment_reference, file_sha256, json_sha256


def build_ingestion_manifest(
    project_root: Path,
    archive_path: Path,
    dataset_path: Path,
    dataset_release: str,
    dataset_doi: str,
    config_values: dict[str, Any],
    overwrite: bool,
) -> dict[str, Any]:
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
        "config": {"values": config_values, "sha256": json_sha256(config_values)},
        "code_version": build_code_version(project_root),
        "environment": build_environment_reference( project_root, project_root / "environment-nilmtk.yml"),
        "run_parameters": {"overwrite": overwrite},
    }

    return manifest
