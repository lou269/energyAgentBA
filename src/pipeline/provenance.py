from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


def json_sha256(value: Any) -> str:
    serialized_value = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized_value.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def git_output(project_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError(
            f"Could not determine Git version for {project_root}"
        ) from error

    return result.stdout.strip()


def build_source_fingerprint(
    project_root: Path,
    source_paths: Iterable[Path],
) -> dict[str, Any]:
    source_files: set[Path] = set()

    for source_path in source_paths:
        if source_path.is_dir():
            source_files.update(source_path.rglob("*.py"))
        elif source_path.is_file():
            source_files.add(source_path)
        else:
            raise FileNotFoundError(
                f"Source path does not exist: {source_path}"
            )

    if not source_files:
        raise ValueError("No source files found for fingerprint.")

    file_hashes = {
        str(path.relative_to(project_root)): file_sha256(path)
        for path in sorted(source_files, key=str)
    }

    return {
        "sha256": json_sha256(file_hashes),
        "files": file_hashes,
    }