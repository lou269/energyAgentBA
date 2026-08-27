# python -m src.analysis.analysis_runner

from __future__ import annotations

import logging
from collections.abc import Mapping

from nilmtk import DataSet

from src.analysis.diagnostics.channel_quality import build_channel_quality
from src.analysis.diagnostics.house_eligibility import build_house_eligibility
from src.analysis.inventory.channel_registry import build_channel_registry
from src.analysis.io import load_or_build_csv, load_or_build_csv_pair
from src.analysis.selection.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from src.analysis.selection.candidate_profiling import build_candidate_profiles
from src.analysis.selection.provisional_selection import build_provisional_selection
from src.config.analysis_config import AnalysisConfig
from src.config.project_config import ProjectConfig, ensure_project_directories


logger = logging.getLogger(__name__)


class AnalysisRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        analysis_config: AnalysisConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.analysis_config = analysis_config or AnalysisConfig()

    def run(self, overwrite: Mapping[str, bool] | None = None) -> None:
        ensure_project_directories(self.project_config)

        overwrite = overwrite or {}
        dataset = DataSet(self.project_config.dataset_path)

        logger.info("Starting analysis pipeline.")

        # Step 1: Build the complete channel inventory.
        logger.info("Building channel registry...")
        channel_registry = load_or_build_csv(
            output_path=self.project_config.meta_output_dir,
            filename="channel_registry",
            overwrite=overwrite.get("channel_registry", False),
            build=lambda: build_channel_registry(
                dataset=dataset,
                canonical_ac_type=self.analysis_config.canonical_ac_type,
            ),
        )
        logger.info("Channel registry completed.")

        # Step 2: Analyze channel quality and identify good sections.
        logger.info("Building channel quality...")
        channel_quality, good_sections = load_or_build_csv_pair(
            output_path=self.project_config.diagnostics_output_dir,
            first_filename="channel_quality",
            second_filename="good_sections",
            overwrite=overwrite.get("channel_quality", False),
            build=lambda: build_channel_quality(
                dataset=dataset,
                channel_registry=channel_registry,
                canonical_ac_type=self.analysis_config.canonical_ac_type,
                chunksize=None,
            ),
        )
        logger.info("Channel quality completed.")

        # Step 3: Determine eligible houses.
        logger.info("Building house eligibility...")
        house_eligibility = load_or_build_csv(
            output_path=self.project_config.diagnostics_output_dir,
            filename="house_eligibility",
            overwrite=overwrite.get("house_eligibility", False),
            build=lambda: build_house_eligibility(
                channel_registry=channel_registry,
                channel_quality=channel_quality,
                min_valid_sample_count=self.analysis_config.min_valid_sample_count,
            ),
        )
        logger.info("House eligibility completed.")

        # Step 4: Build profiles for eligible candidates.
        logger.info("Building candidate profiles...")
        profiles = load_or_build_csv(
            output_path=self.project_config.selection_output_dir,
            filename="profiles",
            overwrite=overwrite.get("profiles", False),
            build=lambda: build_candidate_profiles(
                channel_registry=channel_registry,
                channel_quality=channel_quality,
                house_eligibility=house_eligibility,
                good_sections=good_sections,
            ),
        )
        logger.info("Candidate profiles completed.")

        # Step 5: Select provisional candidates.
        logger.info("Building provisional selection...")
        provisional_selection = load_or_build_csv(
            output_path=self.project_config.selection_output_dir,
            filename="provisional_selection",
            overwrite=overwrite.get("provisional_selection", False),
            build=lambda: build_provisional_selection(
                candidate_profiles=profiles,
                min_longest_segment_days=self.analysis_config.min_longest_segment_days,
            ),
        )
        logger.info("Provisional selection completed.")

        # Step 6: Select available auxiliary appliances.
        logger.info("Building auxiliary appliance selection...")
        load_or_build_csv(
            output_path=self.project_config.selection_output_dir,
            filename="auxiliary_appliance_selection",
            overwrite=overwrite.get(
                "auxiliary_appliance_selection",
                False,
            ),
            build=lambda: build_auxiliary_appliance_selection(
                candidate_profiles=profiles,
                provisional_selection=provisional_selection,
                channel_registry=channel_registry,
                channel_quality=channel_quality,
                good_sections=good_sections,
                min_window_coverage_share=self.analysis_config.min_auxiliary_window_coverage_share,
            ),
        )
        logger.info("Auxiliary appliance selection completed.")

        logger.info("Analysis pipeline completed successfully.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    AnalysisRunner().run(
        overwrite={
            "channel_registry": False,
            "channel_quality": False,
            "house_eligibility": False,
            "profiles": False,
            "provisional_selection": False,
            "auxiliary_appliance_selection": False,
        }
    )


if __name__ == "__main__":
    main()