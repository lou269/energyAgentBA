# python -m src.ingestion.ingestion_runner

from __future__ import annotations

import logging
from pathlib import Path

from src.config.project_config import ProjectConfig, ensure_project_directories
from src.ingestion.downloader import download_dataset_raw
from src.ingestion.converter import convert_raw_to_hdf5

logger = logging.getLogger(__name__)

class IngestionRunner:
    def __init__(self, config: ProjectConfig | None = None) -> None:
        self.config = config or ProjectConfig()

    def run(self, overwrite: bool = False) -> Path:

        ensure_project_directories(self.config)

        logger.info("Start UK-DALE ingestion")

        download_dataset_raw(
            raw_dir=self.config.raw_dir,
            meta_dir=self.config.meta_dir,
            url_base=self.config.url_base,
            url_metadata=self.config.url_metadata,
            houses=self.config.houses,
            metadata_files=self.config.metadata_files,
            overwrite=overwrite,
        )
        
        logger.info("Finished downloading UK-DALE raw data")

        hdf5_path = convert_raw_to_hdf5(
            raw_dir=self.config.raw_dir,
            processed_dir=self.config.processed_dir,
            meta_dir=self.config.meta_dir,
            houses=self.config.houses,
            metadata_files=self.config.metadata_files,
            overwrite=overwrite,
        )

        logger.info("Finished UK-DALE ingestion: %s", hdf5_path)
        return hdf5_path
    
    
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    IngestionRunner().run()
    

if __name__ == "__main__":
    main()