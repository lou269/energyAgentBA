# python -m src.analysis.analysis_runner

from __future__ import annotations

import logging

from nilmtk import DataSet

from src.analysis.diagnostics.channel_quality import build_channel_quality
from src.analysis.diagnostics.house_eligibility import build_house_eligibility
from src.analysis.inventory.channel_registry import build_channel_registry
from src.analysis.io import df_to_csv
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

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        dataset = DataSet(self.project_config.dataset_path)
        logger.info("Starting analysis pipeline...")

        # 3. Metadata inventory
        logger.info("Building channel registry...")

        channel_registry_df = build_channel_registry(
            dataset=dataset,
            canonical_ac_type=self.analysis_config.canonical_ac_type,
        )

        df_to_csv(channel_registry_df, self.project_config.meta_output_dir, "channel_registry")

        logger.info("Channel registry built with %d rows.", len(channel_registry_df))

        # 4. Raw diagnostics
        logger.info("Building channel quality and good sections...")

        channel_quality_df, good_sections_df = build_channel_quality(
            dataset=dataset,
            channel_registry=channel_registry_df,
            canonical_ac_type=self.analysis_config.canonical_ac_type,
            chunksize=None,
        )

        df_to_csv(channel_quality_df, self.project_config.diagnostics_output_dir, "channel_quality")
        df_to_csv(good_sections_df, self.project_config.diagnostics_output_dir, "good_sections")

        logger.info(
            "Channel quality built with %d channels and %d good sections.",
            len(channel_quality_df),
            len(good_sections_df),
        )

        logger.info("Building house eligibility...")

        house_eligibility_df = build_house_eligibility(
            channel_registry=channel_registry_df,
            channel_quality=channel_quality_df,
            min_valid_sample_count=self.analysis_config.min_valid_sample_count,
        )

        df_to_csv(house_eligibility_df, self.project_config.diagnostics_output_dir, "house_eligibility")

        logger.info("House eligibility built with %d rows.", len(house_eligibility_df))

        # 5. Candidate quality profiling
        logger.info("Building candidate profiles...")

        profiles_df = build_candidate_profiles(
            channel_registry=channel_registry_df,
            channel_quality=channel_quality_df,
            house_eligibility=house_eligibility_df,
            good_sections=good_sections_df,
        )

        df_to_csv(profiles_df, self.project_config.selection_output_dir, "profiles")

        logger.info("Candidate profiles built with %d rows.", len(profiles_df))

        # 6. Provisional selection
        logger.info("Building provisional selection...")

        provisional_selection_df = build_provisional_selection(
            candidate_profiles=profiles_df,
            min_longest_segment_days=self.analysis_config.min_longest_segment_days,
        )

        df_to_csv(provisional_selection_df, self.project_config.selection_output_dir, "provisional_selection",)

        logger.info("Provisional selection built with %d rows.", len(provisional_selection_df))

        # 7. Auxiliary appliance selection
        logger.info("Building auxiliary appliance selection...")

        auxiliary_selection_df = build_auxiliary_appliance_selection(
            candidate_profiles=profiles_df,
            provisional_selection=provisional_selection_df,
            channel_registry=channel_registry_df,
            channel_quality=channel_quality_df,
            good_sections=good_sections_df,
            min_window_coverage_share=self.analysis_config.min_auxiliary_window_coverage_share,
            max_balance_channels=self.analysis_config.max_balance_channels,
            max_explanation_channels=self.analysis_config.max_explanation_channels,
        )

        df_to_csv(auxiliary_selection_df, self.project_config.selection_output_dir, "auxiliary_appliance_selection")

        logger.info(
            "Auxiliary appliance selection built with %d rows.",
            len(auxiliary_selection_df)
        )
        
        logger.info("Analysis pipeline completed successfully.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    AnalysisRunner().run()


if __name__ == "__main__":
    main()