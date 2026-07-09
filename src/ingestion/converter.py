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
    if not _validate_metadata(meta_dir=meta_dir, houses=houses, metadata_files=metadata_files):
        raise ValueError("Invalid metadata")

    output_path = processed_dir / "ukdale.h5"
    
    if output_path.exists():
        if not overwrite:
            #logger.info("Skip existing HDF5 file: %s", output_path)
            return output_path

        logger.info("Remove existing HDF5 file: %s", output_path)
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Convert UK-DALE raw data to NILMTK HDF5: %s -> %s", raw_dir, output_path)

    convert_ukdale(
        ukdale_path=str(raw_dir),
        output_filename=str(output_path),
        format="HDF",
    )

    if not output_path.exists():
        raise RuntimeError(f"NILMTK conversion did not create output file: {output_path}")

    logger.info("Created HDF5 file: %s", output_path)
    return output_path



    
def _normalize_house(house: str | int) -> tuple[str, int]:
    house = str(house).strip()

    if house.startswith("house_"):
        number = int(house.replace("house_", ""))
    elif house.startswith("house"):
        number = int(house.replace("house", ""))
    else:
        number = int(house)

    return f"house_{number}", number


def _validate_metadata(
    meta_dir: Path,
    houses: list[str],
    metadata_files: list[str]
) -> bool:
    
    required = [
        meta_dir / filename
        for filename in metadata_files
    ]

    for house_name in houses:
        _, house_number = _normalize_house(house_name)
        required.append(meta_dir / f"building{house_number}.yaml")

    missing = [path for path in required if not path.exists()]

    if missing:
        raise FileNotFoundError(
            "Missing UK-DALE NILM metadata files: "
            + ", ".join(str(path) for path in missing)
        )

    return missing == []
    
