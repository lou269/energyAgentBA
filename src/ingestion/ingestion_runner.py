# python -m src.ingestion.ingestion_runner

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.config.project_config import ProjectConfig, ensure_project_directories
from src.ingestion.converter import convert_raw_to_hdf5
from src.ingestion.downloader import download_dataset_raw

logger = logging.getLogger(__name__)


class IngestionRunner:
    def __init__(
        self,
        config: ProjectConfig | None = None,
    ) -> None:
        self.config = config or ProjectConfig()

    def run(self, overwrite: bool = False) -> Path:
        ensure_project_directories(self.config)

        logger.info("Start ingestion: %s, DOI %s", self.config.dataset_release, self.config.dataset_doi)

        houses, metadata_files = download_dataset_raw(
            raw_dir=self.config.raw_dir,
            meta_dir=self.config.meta_dir,
            archive_path=self.config.archive_path,
            url_data=self.config.url_data,
            url_metadata=self.config.url_metadata,
            overwrite=overwrite,
        )

        logger.info("UK-DALE raw data available: %s", self.config.raw_dir)

        hdf5_path = convert_raw_to_hdf5(
            raw_dir=self.config.raw_dir,
            output_path=self.config.dataset_path,
            meta_dir=self.config.meta_dir,
            houses=houses,
            metadata_files=metadata_files,
            overwrite=overwrite,
        )

        logger.info("Finished UK-DALE ingestion: %s", hdf5_path)
        return hdf5_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and convert UK-DALE.")
    
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Download and convert UK-DALE again.",
    )
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    IngestionRunner().run(overwrite=arguments.overwrite)


if __name__ == "__main__":
    main()