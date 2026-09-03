# python -m pytest tests/unit/test_ingestion.py -v

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.ingestion import converter
from src.ingestion import downloader


def test_download_continues_partial_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "dataset.zip"
    partial_path = tmp_path / "dataset.zip.part"
    partial_path.write_bytes(b"abc")

    def fake_run(command: list[str], **_: object) -> None:
        assert command[command.index("--continue-at") + 1] == "-"
        curl_output_path = Path(
            command[command.index("--output") + 1]
        )
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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


def test_empty_hdf5_file_is_rejected(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "dataset.h5"
    output_path.touch()

    with pytest.raises(RuntimeError, match="Missing or empty"):
        converter._validate_hdf5_output(
            output_path=output_path,
            expected_house_numbers=[1],
        )


def test_damaged_hdf5_file_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "dataset.h5"
    output_path.write_bytes(b"damaged")

    def fail_to_open(_: str) -> None:
        raise OSError("Invalid HDF5")

    monkeypatch.setattr(converter, "DataSet", fail_to_open)

    with pytest.raises(RuntimeError, match="Invalid NILMTK HDF5"):
        converter._validate_hdf5_output(
            output_path=output_path,
            expected_house_numbers=[1],
        )


def test_hdf5_with_missing_building_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "dataset.h5"
    output_path.write_bytes(b"non-empty")

    store = Mock()
    dataset = SimpleNamespace(
        store=store,
        buildings={1: object()},
    )

    monkeypatch.setattr(
        converter,
        "DataSet",
        lambda _: dataset,
    )

    with pytest.raises(RuntimeError, match="missing buildings: 2"):
        converter._validate_hdf5_output(
            output_path=output_path,
            expected_house_numbers=[1, 2],
        )

    store.close.assert_called_once_with()