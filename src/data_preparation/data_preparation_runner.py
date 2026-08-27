# python -m src.data_preparation.data_preparation_runner

from __future__ import annotations

import logging

import pandas as pd
from nilmtk import DataSet

from src.analysis.io import df_to_csv
from src.config.data_preparation_config import DataPreparationConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.data_preparation.selected_data import build_selected_data
from src.data_preparation.selected_candidate_validation import build_selected_candidate_validation, select_candidate_role




logger = logging.getLogger(__name__)


class DataPreparationRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        data_config: DataPreparationConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.data_config = data_config or DataPreparationConfig()

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        dataset = DataSet(self.project_config.dataset_path)

        logger.info("Starting data preparation pipeline...")

        # Load analysis results
        channel_registry_df = pd.read_csv(self.project_config.meta_output_dir / "channel_registry.csv")
        profiles_df = pd.read_csv(self.project_config.selection_output_dir / "profiles.csv")
        provisional_selection_df = pd.read_csv(self.project_config.selection_output_dir / "provisional_selection.csv")
        auxiliary_selection_df = pd.read_csv(self.project_config.selection_output_dir / "auxiliary_appliance_selection.csv")    

        # 8. Selected data extraction + temporal alignment
        logger.info("Building selected aligned data...")
        
        aligned_data, selected_channels_df = build_selected_data(
            dataset=dataset,
            candidate_profiles=profiles_df,
            provisional_selection=provisional_selection_df,
            auxiliary_selection=auxiliary_selection_df,
            channel_registry=channel_registry_df,
            sample_period=self.data_config.alignment_sample_period_seconds,
            canonical_ac_type=self.data_config.canonical_ac_type,
            include_fallback=self.data_config.include_fallback,
            chunksize=None,
        )
        
        df_to_csv(
            selected_channels_df,
            self.project_config.preparation_output_dir,
            "selected_channels",
        )                
        
        for selection_role, frame in aligned_data.items():
            df_to_csv(
                frame.reset_index(),
                self.project_config.preparation_output_dir,
                f"selected_data_{selection_role}",
            )
        
        logger.info(
            "Selected data built: %d channels, roles=%s.",
            len(selected_channels_df),
            list(aligned_data),
        )
        
        # 9. Post-alignment validation
        logger.info("Validating selected candidates...")
        
        channel_validation_df, candidate_validation_df = build_selected_candidate_validation(
            aligned_data=aligned_data,
            manifest=selected_channels_df,
            sample_period=self.data_config.alignment_sample_period_seconds,
            min_mains_coverage_share=self.data_config.min_mains_coverage_share,
            min_mains_valid_duration_days=self.data_config.min_mains_valid_duration_days
        )
        
        selected_role = select_candidate_role(candidate_validation_df)

        if selected_role is None:
            raise ValueError(
                "Neither primary nor fallback passed validation. "
                "See candidate_validation.csv."
            )
        
        df_to_csv(
            channel_validation_df,
            self.project_config.validation_output_dir,
            "channel_validation",
        )
        df_to_csv(
            candidate_validation_df,
            self.project_config.validation_output_dir,
            "candidate_validation",
        )
        
        if selected_role is None:
            raise ValueError(
                "Neither primary nor fallback passed validation. "
                "See candidate_validation.csv."
            )
        
        logger.info("Selected canonical candidate role: %s.", selected_role)
        
        # 10. Canonical selection        
        canonical_manifest = selected_channels_df.loc[
            selected_channels_df["selection_role"].eq(
                selected_role
            )
            & selected_channels_df["channel_role"].eq("mains")
        ].copy()

        mains_keys = (
            canonical_manifest["meter_key"]
            .astype(str)
            .tolist()
        )

        canonical_data = (
            aligned_data[selected_role]
            .loc[:, mains_keys]
            .copy()
        )

        df_to_csv(
            canonical_manifest,
            self.project_config.canonical_output_dir,
            "canonical_manifest",
        )

        df_to_csv(
            canonical_data.reset_index(),
            self.project_config.canonical_output_dir,
            "canonical_data",
        )
        


        logger.info(
            "Data preparation completed successfully. "
            "Canonical role: %s",
            selected_role,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    DataPreparationRunner().run()


if __name__ == "__main__":
    main()

