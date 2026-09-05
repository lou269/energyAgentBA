from __future__ import annotations

from pathlib import Path

from nilmtk import DataSet
from nilmtk.dataset_converters.ukdale.convert_ukdale import convert_ukdale

from src.ingestion.downloader import _parse_house_number


def convert_raw_to_hdf5(
    raw_dir: Path,
    output_path: Path,
    meta_dir: Path,
    houses: list[str],
    metadata_files: list[str],
    overwrite: bool,
) -> Path:
    house_numbers = [_parse_house_number(house) for house in houses]

    if output_path.exists() and not overwrite:
        _validate_hdf5_output(output_path, house_numbers)
        return output_path


    required_metadata = {
        "dataset.yaml",
        "meter_devices.yaml",
    }
    
    required_metadata.update(
        f"building{house_number}.yaml"
        for house_number in house_numbers
    )

    available_metadata = set(metadata_files)
    missing_metadata = [
        meta_dir / filename
        for filename in sorted(required_metadata)
        if filename not in available_metadata
        or not (meta_dir / filename).is_file()
    ]
    if missing_metadata:
        raise FileNotFoundError("Missing UK-DALE NILMTK metadata files: " + ", ".join(str(path) for path in missing_metadata))

    temp_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    temp_path.unlink(missing_ok=True)

    try:
        convert_ukdale(
            ukdale_path=str(raw_dir),
            output_filename=str(temp_path),
            format="HDF",
        )

        _validate_hdf5_output(temp_path, house_numbers)
        temp_path.replace(output_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return output_path


def _validate_hdf5_output(
    output_path: Path,
    expected_house_numbers: list[int],
) -> None:
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty NILMTK HDF5 file: {output_path}")

    try:
        dataset = DataSet(str(output_path))
    except Exception as error:
        raise RuntimeError(f"Invalid NILMTK HDF5 file: {output_path}") from error

    store = dataset.store
    if store is None:
        raise RuntimeError(f"NILMTK HDF5 file has no datastore: {output_path}")

    try:
        available_buildings = set(dataset.buildings)
    finally:
        store.close()

    missing_buildings = sorted(set(expected_house_numbers) - available_buildings)
    if missing_buildings:
        raise RuntimeError("NILMTK HDF5 file is missing buildings: "+ ", ".join(str(number) for number in missing_buildings))