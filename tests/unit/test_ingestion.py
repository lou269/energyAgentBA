# python -m pytest tests/unit/test_ingestion.py -v

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from src.ingestion import converter
from src.ingestion import downloader


def test_download_continues_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "dataset.zip"
    partial_path = tmp_path / "dataset.zip.part"
    partial_path.write_bytes(b"abc")

    def fake_run(command: list[str], **_: object) -> None:
        assert command[command.index("--continue-at") + 1] == "-"
        curl_output_path = Path(command[command.index("--output") + 1])
        assert curl_output_path == partial_path

        with curl_output_path.open("ab") as file:
            file.write(b"def")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)

    downloader._download_file(
        url="https://example.test/dataset.zip",
        output_path=output_path,
        expected_size=6,
        overwrite=False,
    )

    assert output_path.read_bytes() == b"abcdef"
    assert not partial_path.exists()


def test_download_rejects_wrong_file_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "dataset.zip"
    output_path.write_bytes(b"wrong-size")

    def fail_if_called(*_: object, **__: object) -> None:
        pytest.fail("curl must not be called for an existing file")

    monkeypatch.setattr(downloader.subprocess, "run", fail_if_called)

    with pytest.raises(ValueError, match="expected 3 bytes"):
        downloader._download_file(
            url="https://example.test/dataset.zip",
            output_path=output_path,
            expected_size=3,
            overwrite=False,
        )


def test_download_overwrites_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "dataset.zip"
    partial_path = tmp_path / "dataset.zip.part"

    output_path.write_bytes(b"old")
    partial_path.write_bytes(b"partial")

    def fake_run(command: list[str], **_: object) -> None:
        assert not output_path.exists()
        assert not partial_path.exists()

        curl_output_path = Path(command[command.index("--output") + 1])
        curl_output_path.write_bytes(b"new")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)

    downloader._download_file(
        url="https://example.test/dataset.zip",
        output_path=output_path,
        expected_size=3,
        overwrite=True,
    )

    assert output_path.read_bytes() == b"new"
    assert not partial_path.exists()


def test_empty_hdf5_file_is_rejected(tmp_path: Path) -> None:
    output_path = tmp_path / "dataset.h5"
    output_path.touch()

    with pytest.raises(RuntimeError, match="Missing or empty"):
        converter._validate_hdf5_output(
            output_path=output_path, expected_house_numbers=[1]
        )


def test_damaged_hdf5_file_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "dataset.h5"
    output_path.write_bytes(b"damaged")

    def fail_to_open(_: str) -> None:
        raise OSError("Invalid HDF5")

    monkeypatch.setattr(converter, "DataSet", fail_to_open)

    with pytest.raises(RuntimeError, match="Invalid NILMTK HDF5"):
        converter._validate_hdf5_output(
            output_path=output_path, expected_house_numbers=[1]
        )


def test_hdf5_with_missing_building_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "dataset.h5"
    output_path.write_bytes(b"non-empty")

    store = Mock()
    dataset = SimpleNamespace(store=store, buildings={1: object()})

    monkeypatch.setattr(converter, "DataSet", lambda _: dataset)

    with pytest.raises(RuntimeError, match="missing buildings: 2"):
        converter._validate_hdf5_output(
            output_path=output_path, expected_house_numbers=[1, 2]
        )

    store.close.assert_called_once_with()


def test_extraction_is_skipped_once_marker_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_dir = tmp_path / "raw"
    meta_dir = tmp_path / "meta"
    archive_path = tmp_path / "dataset.zip"

    with ZipFile(archive_path, "w") as archive:
        archive.writestr("house_1/labels.dat", "1,fridge\n")

    archive_size = archive_path.stat().st_size

    def fake_listing(directory_url: str) -> list[dict[str, object]]:
        if directory_url == "https://example.test/data":
            return [{"name": archive_path.name, "download": "unused", "size": archive_size}]
        return []

    monkeypatch.setattr(downloader, "_load_file_listing", fake_listing)

    houses, metadata_files = downloader.download_dataset_raw(
        raw_dir=raw_dir,
        meta_dir=meta_dir,
        archive_path=archive_path,
        url_data="https://example.test/data",
        url_metadata="https://example.test/meta",
        overwrite=False,
    )

    assert houses == ["house_1"]
    assert metadata_files == []

    extracted_file = raw_dir / "house_1" / "labels.dat"
    assert extracted_file.is_file()
    assert (raw_dir / ".extraction_complete").is_file()

    extracted_file.unlink()

    downloader.download_dataset_raw(
        raw_dir=raw_dir,
        meta_dir=meta_dir,
        archive_path=archive_path,
        url_data="https://example.test/data",
        url_metadata="https://example.test/meta",
        overwrite=False,
    )

    assert not extracted_file.exists()


def test_convert_rejects_incomplete_metadata(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    (meta_dir / "dataset.yaml").write_text("name: UK-DALE")

    output_path = tmp_path / "dataset.h5"

    with pytest.raises(FileNotFoundError) as excinfo:
        converter.convert_raw_to_hdf5(
            raw_dir=raw_dir,
            output_path=output_path,
            meta_dir=meta_dir,
            houses=["house_1"],
            metadata_files=["dataset.yaml", "meter_devices.yaml"],
            overwrite=False,
        )

    message = str(excinfo.value)
    assert "building1.yaml" in message
    assert "meter_devices.yaml" in message
    assert "dataset.yaml" not in message
