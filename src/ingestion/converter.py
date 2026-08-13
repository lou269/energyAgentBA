from __future__ import annotations

from pathlib import Path
import logging
from nilmtk.dataset_converters.ukdale.convert_ukdale import convert_ukdale

logger = logging.getLogger(__name__)


def convert_raw_to_hdf5(
    raw_dir: Path,
    processed_dir: Path,
    meta_dir: Path,
    houses: list[str],
    metadata_files: list[str],
    overwrite: bool = False,
) -> Path:
    _validate_metadata(
        meta_dir=meta_dir,
        houses=houses,
        metadata_files=metadata_files,
    )
    
    output_path = processed_dir / "ukdale.h5"
    
    if output_path.exists():
        if not overwrite:
            return output_path
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    convert_ukdale(
        ukdale_path=str(raw_dir),
        output_filename=str(output_path),
        format="HDF",
    )

    if not output_path.exists():
        raise RuntimeError(f"NILMTK conversion did not create output file: {output_path}")

    return output_path



def _validate_metadata(
    meta_dir: Path,
    houses: list[str],
    metadata_files: list[str]
) -> None:
    
    required = [
        meta_dir / filename
        for filename in metadata_files
    ]

    for house in houses:
        house_number = int(house.split("_")[1])
        required.append(meta_dir / f"building{house_number}.yaml")

    missing = [path for path in required if not path.exists()]

    if missing:
        raise FileNotFoundError(
            "Missing UK-DALE NILM metadata files: " + ", ".join(str(path) for path in missing)
        )
    
