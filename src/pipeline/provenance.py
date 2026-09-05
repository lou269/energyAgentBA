from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


def json_sha256(value: Any) -> str:
    serialized_value = json.dumps(value, sort_keys=True, separators=(",", ":"))
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
        raise RuntimeError(f"Could not determine Git version for {project_root}") from error

    return result.stdout.strip()


def build_code_version(project_root: Path) -> dict[str, Any]:
    return {
        "git_commit": git_output(project_root, "rev-parse", "HEAD"),
        "git_dirty": bool(git_output(project_root, "status", "--porcelain")),
    }


def build_environment_reference(project_root: Path, env_file: Path) -> dict[str, Any]:
    return {
        "file": str(env_file.relative_to(project_root)),
        "sha256": file_sha256(env_file),
    }


def build_file_metadata(project_root: Path, path: Path) -> dict[str, Any]:
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