# python -m src.diagnostics.diagnostic_runner

from __future__ import annotations

import logging

from nilmtk import DataSet

from src.diagnostics.channel_quality import build_channel_quality
from src.diagnostics.channel_registry import build_channel_registry
from src.config.config_nilmtk import DiagnosticsConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


class DiagnosticsRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        diagnostics_config: DiagnosticsConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.diagnostics_config = diagnostics_config or DiagnosticsConfig()

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        dataset = DataSet(self.project_config.dataset_path)

        logger.info("Starting diagnostics.")

        logger.info("Building channel registry...")

        channel_registry = build_channel_registry(
            dataset=dataset,
            canonical_ac_type=self.diagnostics_config.canonical_ac_type,
        )

        df_to_csv(
            df=channel_registry,
            output_path=self.project_config.meta_output_dir,
            filename="channel_registry",
        )

        logger.info("Building channel quality...")

        channel_quality = build_channel_quality(
            dataset=dataset,
            channel_registry=channel_registry,
            canonical_ac_type=self.diagnostics_config.canonical_ac_type,
            chunksize=self.diagnostics_config.channel_quality_chunksize,
        )

        df_to_csv(
            df=channel_quality,
            output_path=self.project_config.diagnostics_output_dir,
            filename="channel_quality",
        )

        logger.info("Diagnostics completed successfully.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    DiagnosticsRunner().run()


if __name__ == "__main__":
    main()
