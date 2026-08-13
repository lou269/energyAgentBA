from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

logger = logging.getLogger(__name__)

LABELS_PATTERN = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")

def download_dataset_raw(
    raw_dir: Path,
    meta_dir: Path,
    url_base: str,
    url_metadata: str,
    houses: list[str],
    metadata_files: list[str],
    overwrite: bool = False,
) -> None:    
    
    _download_metadata(
        meta_dir=meta_dir,
        url_metadata=url_metadata,
        houses=houses,
        metadata_files=metadata_files,
        overwrite=overwrite,
    )
    
    for house in houses:
        _download_house(
            raw_dir=raw_dir,
            house_name=house,
            url_base=url_base,
            overwrite=overwrite,
        )


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
    

        
def _download_file(url: str, output_path: Path, overwrite: bool = False) -> bool:
    if output_path.exists() and not overwrite:
        return True

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")


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
    url: str,
    output_path: Path,
    overwrite: bool = False,
) -> None:
    if not _download_file(url=url, output_path=output_path, overwrite=overwrite):
        raise RuntimeError(f"Required file could not be downloaded: {url}")


def _download_optional_file(
    url: str,
    output_path: Path,
    overwrite: bool = False,
) -> None:
    success = _download_file(url=url, output_path=output_path, overwrite=overwrite)

    if not success:
        logger.info("Optional file not available, continue: %s", url)



def _download_metadata(
    meta_dir: Path,
    url_metadata: str,
    houses: list[str],
    metadata_files: list[str],
    overwrite: bool = False,
) -> None:



    for metadata_file in metadata_files:
        output_path = meta_dir / metadata_file
        url = f"{url_metadata.rstrip('/')}/{metadata_file}"
        _download_required_file(url=url, output_path=output_path, overwrite=overwrite)
        
        
  
    for house in houses:
        house_number = int(house.split("_")[1])
        building_url = f"{url_metadata.rstrip('/')}/building{house_number}.yaml"
        building_output_path = meta_dir / f"building{house_number}.yaml"

        _download_required_file(
            url=building_url,
            output_path=building_output_path,
            overwrite=overwrite,
        )
            
            
def _download_house(
    raw_dir: Path,
    house_name: str,
    url_base: str,
    overwrite: bool = False,
) -> None:
    
    house_dir = raw_dir / house_name
    house_dir.mkdir(parents=True, exist_ok=True)

    labels_url = f"{url_base.rstrip('/')}/{house_name}/labels.dat"
    labels_output_path = house_dir / "labels.dat"

    _download_required_file(
        url=labels_url,
        output_path=labels_output_path,
        overwrite=overwrite,
    )
    
    _download_optional_file(
        url=f"{url_base.rstrip('/')}/{house_name}/mains.dat",
        output_path=house_dir / "mains.dat",
        overwrite=overwrite,
    )
    
    labels_map = _parse_labels_file(labels_output_path)


    for channel in labels_map:
        channel_path = house_dir / f"channel_{channel}.dat"

        _download_required_file(
            url=f"{url_base.rstrip('/')}/{house_name}/channel_{channel}.dat",
            output_path=channel_path,
            overwrite=overwrite,
        )
        
    

        
