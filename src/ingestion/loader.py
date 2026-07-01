from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from nilmtk.dataset_converters.ukdale.convert_ukdale import convert_ukdale

from src.config.project_config import ProjectConfig, ensure_project_directories

logger = logging.getLogger(__name__)

UKDALE_METADATA_BASE_URL = (
    "https://raw.githubusercontent.com/JackKelly/UK-DALE_metadata/master"
)

COMMON_METADATA_FILES = ["dataset.yaml", "meter_devices.yaml"]
LABELS_PATTERN = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")


def _url(config: ProjectConfig, relative_path: str) -> str:
    return f"{config.url_base.rstrip('/')}/{relative_path}"


def _metadata_url(relative_path: str) -> str:
    return f"{UKDALE_METADATA_BASE_URL.rstrip('/')}/{relative_path}"


def _normalize_house(house: str | int) -> tuple[str, int]:
    house = str(house).strip()

    if house.startswith("house_"):
        number = int(house.replace("house_", ""))
    elif house.startswith("house"):
        number = int(house.replace("house", ""))
    else:
        number = int(house)

    return f"house_{number}", number


def _selected_houses(
    config: ProjectConfig,
    houses: list[str | int] | None = None,
) -> list[str]:
    return [_normalize_house(house)[0] for house in (houses or config.houses)]


def _is_full_house_scope(
    config: ProjectConfig,
    selected_houses: list[str],
) -> bool:
    configured_houses = {_normalize_house(house)[0] for house in config.houses}
    return set(selected_houses) == configured_houses


def _download_file(url: str, output_path: Path, overwrite: bool = False) -> bool:
    if output_path.exists() and not overwrite:
        logger.info("Skip existing file: %s", output_path)
        return True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    logger.info("Download %s -> %s", url, output_path)

    try:
        with urlopen(url, timeout=60) as response, temp_path.open("wb") as file:
            shutil.copyfileobj(response, file)

        temp_path.replace(output_path)
        return True

    except (HTTPError, URLError, TimeoutError) as error:
        if temp_path.exists():
            temp_path.unlink()

        logger.warning("Download failed for %s: %s", url, error)
        return False


def _download_required_file(
    *,
    url: str,
    output_path: Path,
    overwrite: bool = False,
) -> None:
    if not _download_file(url=url, output_path=output_path, overwrite=overwrite):
        raise RuntimeError(f"Required file could not be downloaded: {url}")


def _download_optional_file(
    *,
    url: str,
    output_path: Path,
    overwrite: bool = False,
) -> bool:
    success = _download_file(url=url, output_path=output_path, overwrite=overwrite)

    if not success:
        logger.info("Optional file not available, continue: %s", url)

    return success


def _parse_labels_file(labels_path: Path) -> dict[int, str]:
    if not labels_path.exists():
        raise FileNotFoundError(f"labels.dat not found: {labels_path}")

    mapping: dict[int, str] = {}

    for raw_line in labels_path.read_text(encoding="utf-8").splitlines():
        match = LABELS_PATTERN.match(raw_line.strip())

        if not match:
            if raw_line.strip():
                logger.warning("Skip unrecognized labels.dat line: %r", raw_line)
            continue

        mapping[int(match.group(1))] = match.group(2).strip()

    if not mapping:
        raise ValueError(f"No channel mappings found in labels.dat: {labels_path}")

    return dict(sorted(mapping.items()))


def _download_metadata(
    raw_dir: Path,
    houses: list[str],
    overwrite: bool,
) -> None:
    metadata_dir = raw_dir / "metadata"

    logger.info("Download UK-DALE NILM metadata for houses: %s", houses)

    for filename in COMMON_METADATA_FILES:
        _download_required_file(
            url=_metadata_url(filename),
            output_path=metadata_dir / filename,
            overwrite=overwrite,
        )

    for house_name in houses:
        _, house_number = _normalize_house(house_name)

        _download_required_file(
            url=_metadata_url(f"building{house_number}.yaml"),
            output_path=metadata_dir / f"building{house_number}.yaml",
            overwrite=overwrite,
        )


def _download_house(
    config: ProjectConfig,
    raw_dir: Path,
    house_name: str,
    overwrite: bool,
) -> None:
    house_dir = raw_dir / house_name

    _download_required_file(
        url=_url(config, f"{house_name}/labels.dat"),
        output_path=house_dir / "labels.dat",
        overwrite=overwrite,
    )

    _download_optional_file(
        url=_url(config, f"{house_name}/mains.dat"),
        output_path=house_dir / "mains.dat",
        overwrite=overwrite,
    )

    labels_map = _parse_labels_file(house_dir / "labels.dat")
    logger.info("Found %s labeled channels for %s", len(labels_map), house_name)

    missing_channels: list[int] = []

    for channel in labels_map:
        channel_path = house_dir / f"channel_{channel}.dat"

        success = _download_file(
            url=_url(config, f"{house_name}/channel_{channel}.dat"),
            output_path=channel_path,
            overwrite=overwrite,
        )

        if not success:
            missing_channels.append(channel)

    if missing_channels:
        raise RuntimeError(
            f"Missing required channel files for {house_name}: {missing_channels}"
        )


def _validate_metadata(raw_dir: Path, houses: list[str]) -> None:
    required = [
        raw_dir / "metadata" / filename
        for filename in COMMON_METADATA_FILES
    ]

    for house_name in houses:
        _, house_number = _normalize_house(house_name)
        required.append(raw_dir / "metadata" / f"building{house_number}.yaml")

    missing = [path for path in required if not path.exists()]

    if missing:
        raise FileNotFoundError(
            "Missing UK-DALE NILM metadata files: "
            + ", ".join(str(path) for path in missing)
        )


def _validate_house_structure(raw_dir: Path, house_name: str) -> None:
    house_dir = raw_dir / house_name
    labels_path = house_dir / "labels.dat"

    required = [labels_path]
    missing = [path for path in required if not path.exists()]

    if labels_path.exists():
        labels_map = _parse_labels_file(labels_path)

        for channel in labels_map:
            channel_path = house_dir / f"channel_{channel}.dat"

            if not channel_path.exists():
                missing.append(channel_path)

    if missing:
        raise FileNotFoundError(
            f"Incomplete UK-DALE structure for {house_name}: "
            + ", ".join(str(path) for path in missing)
        )

    mains_path = house_dir / "mains.dat"
    if not mains_path.exists():
        logger.info("Optional mains.dat missing for %s: %s", house_name, mains_path)


def _validate_downloaded_scope(raw_dir: Path, houses: list[str]) -> None:
    _validate_metadata(raw_dir, houses)

    for house_name in houses:
        _validate_house_structure(raw_dir, house_name)


def download_ukdale_raw(
    config: ProjectConfig | None = None,
    houses: list[str | int] | None = None,
    overwrite: bool = False,
) -> Path:
    config = config or ProjectConfig()
    ensure_project_directories(config)

    raw_dir = config.raw_dir
    selected_houses = _selected_houses(config, houses)

    logger.info("Download UK-DALE raw data for houses: %s", selected_houses)

    _download_metadata(
        raw_dir=raw_dir,
        houses=selected_houses,
        overwrite=overwrite,
    )

    for house_name in selected_houses:
        _download_house(
            config=config,
            raw_dir=raw_dir,
            house_name=house_name,
            overwrite=overwrite,
        )

    _validate_downloaded_scope(raw_dir, selected_houses)

    logger.info("UK-DALE raw download completed: %s", raw_dir)
    return raw_dir


def convert_raw_to_hdf5(
    config: ProjectConfig | None = None,
    houses: list[str | int] | None = None,
    overwrite: bool = False,
) -> Path:
    config = config or ProjectConfig()
    ensure_project_directories(config)

    raw_dir = config.raw_dir
    selected_houses = _selected_houses(config, houses)

    if not _is_full_house_scope(config, selected_houses):
        raise ValueError(
            "NILMTK HDF5 conversion to ukdale.h5 is only allowed for the full UK-DALE scope. "
            f"Selected houses: {selected_houses}. "
            "Use download_ukdale_raw(...) for partial test downloads, or convert the full dataset."
        )

    _validate_downloaded_scope(raw_dir, selected_houses)

    output_path = config.processed_dir / "ukdale.h5"

    if output_path.exists():
        if not overwrite:
            logger.info("Skip existing HDF5 file: %s", output_path)
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


def download_and_convert_ukdale(
    config: ProjectConfig | None = None,
    houses: list[str | int] | None = None,
    overwrite: bool = False,
) -> Path:
    config = config or ProjectConfig()

    download_ukdale_raw(
        config=config,
        houses=houses,
        overwrite=overwrite,
    )

    return convert_raw_to_hdf5(
        config=config,
        houses=houses,
        overwrite=overwrite,
    )