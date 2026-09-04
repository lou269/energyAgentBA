from __future__ import annotations

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile
from typing import Any


def download_dataset_raw(
    raw_dir: Path,
    meta_dir: Path,
    archive_path: Path,
    url_data: str,
    url_metadata: str,
    overwrite: bool,
) -> tuple[list[str], list[str]]:
    "Download and extract UK-DALE and download all metadata."
    data_files = _load_file_listing(url_data)

    archive_info = next(
        (
            file_info
            for file_info in data_files
            if file_info["name"] == archive_path.name
        ),
        None,
    )
    if archive_info is None:
        raise FileNotFoundError(f"Archive not listed by CEDA: {archive_path.name}")

    _download_file(
        url=str(archive_info["download"]),
        output_path=archive_path,
        expected_size=int(archive_info["size"]),
        overwrite=overwrite,
    )

    with ZipFile(archive_path) as archive:
        houses = sorted(
            {
                Path(member).parts[0]
                for member in archive.namelist()
                if member.startswith("house_")
            },
            key=lambda house: int(house[len("house_") :]),
        )

        if not houses:
            raise ValueError("No UK-DALE houses found in archive")

        raw_data_exists = all(
            (raw_dir / house / "labels.dat").is_file() for house in houses
        )

        if overwrite or not raw_data_exists:
            raw_dir.mkdir(parents=True, exist_ok=True)
            archive.extractall(raw_dir)

    metadata_info = [
        file_info
        for file_info in _load_file_listing(url_metadata)
        if file_info["type"] == "file"
    ]

    for file_info in metadata_info:
        _download_file(
            url=str(file_info["download"]),
            output_path=meta_dir / str(file_info["name"]),
            expected_size=int(file_info["size"]),
            overwrite=overwrite,
        )

    metadata_files = [str(file_info["name"]) for file_info in metadata_info]
    return houses, metadata_files


def _load_file_listing(directory_url: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            f"{directory_url.rstrip('/')}?json=",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["items"]


def _download_file(
    url: str, output_path: Path, expected_size: int, overwrite: bool
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_suffix(output_path.suffix + ".part")

    if overwrite:
        output_path.unlink(missing_ok=True)
        partial_path.unlink(missing_ok=True)

    if output_path.exists():
        _validate_size(output_path, expected_size)
        return

    if partial_path.exists() and partial_path.stat().st_size == expected_size:
        partial_path.replace(output_path)
        return

    subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--continue-at",
            "-",
            "--output",
            str(partial_path),
            url,
        ],
        check=True,
    )

    _validate_size(partial_path, expected_size)
    partial_path.replace(output_path)


def _validate_size(path: Path, expected_size: int) -> None:
    actual_size = path.stat().st_size

    if actual_size != expected_size:
        raise ValueError(
            f"Invalid file size for {path}: expected {expected_size} bytes, got {actual_size} bytes"
        )
