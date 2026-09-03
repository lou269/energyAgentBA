from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import platform
from typing import Any

from src.pipeline.provenance import (
    build_source_fingerprint,
    file_sha256,
    git_output,
    json_sha256,
)


def build_forecast_run_manifest(
    project_root: Path,
    run_id: str,
    experiment_id: str,
    split: str,
    candidate_id: str,
    config_values: dict[str, Any],
    source_paths: tuple[Path, ...],
    input_paths: Mapping[str, Path],
    output_paths: Mapping[str, Path],
    split_boundaries: Mapping[str, Any],
    forecast_origins: tuple[Any, ...],
    model_parameters: Mapping[str, Any],
    seasonalities: Mapping[str, Any],
    history_rules: Mapping[str, Any],
    metric_definitions: Mapping[str, Any],
    exclusion_rules: Mapping[str, Any],
    primary_naive_reference: str | None,
    seed: int,
    uncertainty_samples: int,
    runtime_seconds: float,
) -> dict[str, Any]:
    if not run_id:
        raise ValueError("run_id must not be empty.")

    if not experiment_id:
        raise ValueError("experiment_id must not be empty.")

    if split not in {"validation", "test"}:
        raise ValueError(f"Unsupported split: {split}")

    if runtime_seconds < 0:
        raise ValueError("runtime_seconds must not be negative.")

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
        "experiment_id": experiment_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "candidate_id": candidate_id,
        "inputs": inputs,
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
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "pandas": version("pandas"),
            "prophet": version("prophet"),
        },
        "evaluation": {
            "split_boundaries": {
                name: str(value)
                for name, value in split_boundaries.items()
            },
            "forecast_origins": [
                str(origin)
                for origin in forecast_origins
            ],
            "metric_definitions": dict(metric_definitions),
            "exclusion_rules": dict(exclusion_rules),
            "primary_naive_reference": primary_naive_reference,
        },
        "models": {
            "parameters": dict(model_parameters),
            "seasonalities": dict(seasonalities),
            "history_rules": dict(history_rules),
            "seed": seed,
            "uncertainty_samples": uncertainty_samples,
        },
        "runtime_seconds": runtime_seconds,
        "outputs": outputs,
    }


def _build_file_metadata(
    project_root: Path,
    path: Path,
) -> dict[str, Any]:
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