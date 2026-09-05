# python -m src.analysis.analysis_runner

from __future__ import annotations

from dataclasses import asdict
import json
import logging

from nilmtk import DataSet

from src.analysis.analysis_run_manifest import build_analysis_manifest
from src.analysis.diagnostics.channel_quality import build_channel_quality
from src.analysis.diagnostics.house_eligibility import build_house_eligibility
from src.analysis.inventory.channel_registry import build_channel_registry
from src.analysis.selection.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from src.analysis.selection.candidate_profiling import build_candidate_profiles
from src.analysis.selection.provisional_selection import build_candidate_selection_outputs
from src.config.analysis_config import AnalysisConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.pipeline.io import df_to_csv, save_json

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

        logger.info("Starting analysis pipeline.")

        logger.info("Building channel registry...")

        channel_registry = build_channel_registry(
            dataset=dataset,
            canonical_ac_type=self.analysis_config.canonical_ac_type,
        )

        df_to_csv(
            df=channel_registry,
            output_path=self.project_config.meta_output_dir,
            filename="channel_registry",
        )

        logger.info("Building channel quality...")

        channel_quality, good_sections = build_channel_quality(
            dataset=dataset,
            channel_registry=channel_registry,
            canonical_ac_type=self.analysis_config.canonical_ac_type,
            chunksize=self.analysis_config.channel_quality_chunksize,
        )

        df_to_csv(
            df=channel_quality,
            output_path=self.project_config.diagnostics_output_dir,
            filename="channel_quality",
        )

        df_to_csv(
            df=good_sections,
            output_path=self.project_config.diagnostics_output_dir,
            filename="good_sections",
        )

        logger.info("Building house eligibility...")

        house_eligibility = build_house_eligibility(
            channel_registry=channel_registry,
            channel_quality=channel_quality,
            min_valid_sample_count=self.analysis_config.min_valid_sample_count,
        )

        df_to_csv(
            df=house_eligibility,
            output_path=self.project_config.diagnostics_output_dir,
            filename="house_eligibility",
        )

        logger.info("Building candidate profiles...")

        profiles = build_candidate_profiles(
            channel_registry=channel_registry,
            channel_quality=channel_quality,
            house_eligibility=house_eligibility,
            good_sections=good_sections,
        )

        df_to_csv(
            df=profiles,
            output_path=self.project_config.selection_output_dir,
            filename="profiles",
        )

        logger.info("Building candidate selection outputs...")

        provisional_selection, candidate_selection_decisions = build_candidate_selection_outputs(
            candidate_profiles=profiles,
            min_longest_segment_days=self.analysis_config.min_longest_segment_days,
        )

        df_to_csv(
            df=provisional_selection,
            output_path=self.project_config.selection_output_dir,
            filename="provisional_selection",
        )

        df_to_csv(
            df=candidate_selection_decisions,
            output_path=self.project_config.selection_output_dir,
            filename="candidate_selection_decisions",
        )

        logger.info("Building auxiliary appliance selection...")

        auxiliary_appliance_selection = build_auxiliary_appliance_selection(
            candidate_profiles=profiles,
            provisional_selection=provisional_selection,
            channel_registry=channel_registry,
            channel_quality=channel_quality,
            good_sections=good_sections,
        )

        df_to_csv(
            df=auxiliary_appliance_selection,
            output_path=self.project_config.selection_output_dir,
            filename="auxiliary_appliance_selection",
        )

        logger.info("Building analysis manifest...")

        ingestion_manifest_path = self.project_config.meta_output_dir / "ingestion_run_manifest.json"


        ingestion_manifest = json.loads(ingestion_manifest_path.read_text(encoding="utf-8"))

        output_paths = (
            self.project_config.meta_output_dir / "channel_registry.csv",
            self.project_config.diagnostics_output_dir / "channel_quality.csv",
            self.project_config.diagnostics_output_dir / "good_sections.csv",
            self.project_config.diagnostics_output_dir / "house_eligibility.csv",
            self.project_config.selection_output_dir / "profiles.csv",
            self.project_config.selection_output_dir / "provisional_selection.csv",
            self.project_config.selection_output_dir / "candidate_selection_decisions.csv",
            self.project_config.selection_output_dir / "auxiliary_appliance_selection.csv",
        )

        analysis_manifest = build_analysis_manifest(
            project_root=self.project_config.project_root,
            ingestion_run_id=ingestion_manifest["run_id"],
            dataset_path=self.project_config.dataset_path,
            config_values=asdict(self.analysis_config),
            output_paths=output_paths,
        )

        save_json(
            analysis_manifest,
            self.project_config.meta_output_dir / "analysis_run_manifest.json",
        )

        logger.info("Analysis pipeline completed successfully.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    AnalysisRunner().run()


if __name__ == "__main__":
    main()