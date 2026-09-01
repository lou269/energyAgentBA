# python -m src.ingestion.ingestion_runner

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.config.project_config import ProjectConfig, ensure_project_directories
from src.ingestion.converter import convert_raw_to_hdf5
from src.ingestion.downloader import download_dataset_raw
from src.ingestion.ingestion_run_manifest import build_ingestion_manifest
from src.pipeline.io import save_json

logger = logging.getLogger(__name__)


class IngestionRunner:
    def __init__(
        self,
        config: ProjectConfig | None = None,
    ) -> None:
        self.config = config or ProjectConfig()

    def run(self, overwrite: bool = False) -> Path:
        ensure_project_directories(self.config)

        logger.info(
            "Start ingestion: %s, DOI %s",
            self.config.dataset_release,
            self.config.dataset_doi,
        )

        houses, metadata_files = download_dataset_raw(
            raw_dir=self.config.raw_dir,
            meta_dir=self.config.meta_dir,
            archive_path=self.config.archive_path,
            url_data=self.config.url_data,
            url_metadata=self.config.url_metadata,
            overwrite=overwrite,
        )

        logger.info(
            "UK-DALE raw data available: %s",
            self.config.raw_dir,
        )

        hdf5_path = convert_raw_to_hdf5(
            raw_dir=self.config.raw_dir,
            output_path=self.config.dataset_path,
            meta_dir=self.config.meta_dir,
            houses=houses,
            metadata_files=metadata_files,
            overwrite=overwrite,
        )

        ingestion_manifest = build_ingestion_manifest(
            project_root=self.config.project_root,
            archive_path=self.config.archive_path,
            dataset_path=hdf5_path,
            dataset_release=self.config.dataset_release,
            dataset_doi=self.config.dataset_doi,
            config_values={
                "archive_path": str(self.config.archive_path),
                "raw_dir": str(self.config.raw_dir),
                "meta_dir": str(self.config.meta_dir),
                "dataset_path": str(self.config.dataset_path),
                "url_data": self.config.url_data,
                "url_metadata": self.config.url_metadata,
            },
            overwrite=overwrite,
        )
        
        ingestion_manifest_path = self.config.meta_output_dir / "ingestion_run_manifest.json"
        
        save_json(
            ingestion_manifest, 
            ingestion_manifest_path
        )

        logger.info(
            "Saved ingestion manifest: %s",
            ingestion_manifest_path,
        )
        logger.info(
            "Finished UK-DALE ingestion: %s",
            hdf5_path,
        )
        return hdf5_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and convert UK-DALE."
    )
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