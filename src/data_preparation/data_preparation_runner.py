# python -m src.data_preparation.data_preparation_runner

from __future__ import annotations

import logging

import pandas as pd
from nilmtk import DataSet

from src.pipeline.io import df_to_csv
from src.config.config_nilmtk import DataPreparationConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.data_preparation.aggregation.channel_loading import build_loaded_channels
from src.data_preparation.aggregation.aggregation import build_aggregated_data
from src.data_preparation.selection.candidate_availability import build_candidate_availability
from src.data_preparation.selection.candidate_selection import build_candidate_selection



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

        channel_registry_df = pd.read_csv(self.project_config.meta_output_dir / "channel_registry.csv")
        channel_quality_df = pd.read_csv(self.project_config.analysis_output_dir / "channel_quality.csv")

        logger.info("Loading channels from dataset...")
        
        loaded_channels = build_loaded_channels(
            dataset=dataset,
            channel_quality=channel_quality_df,
            canonical_ac_type=self.data_config.canonical_ac_type,
            mains_only=True,
            selected_house_ids=self.data_config.selected_house_ids
        )

        logger.info("Loaded %d channels.", len(loaded_channels))
        
        logger.info("Aggregating channels to 15min and hourly intervals...")

        sample_periods = dict(zip(channel_registry_df["meter_key"], channel_registry_df["sample_period_seconds"]))

        data_15min, quality_15min, data_hourly, quality_hourly = build_aggregated_data(
            channels=loaded_channels,
            sample_periods=sample_periods,
            min_coverage_share=self.data_config.min_coverage_share,
        )

        df_to_csv(data_15min.reset_index(), self.project_config.preparation_output_dir, "data_15min")
        df_to_csv(quality_15min.reset_index(), self.project_config.preparation_output_dir, "quality_15min")
        df_to_csv(data_hourly.reset_index(), self.project_config.preparation_output_dir, "data_hourly")
        df_to_csv(quality_hourly.reset_index(), self.project_config.preparation_output_dir, "quality_hourly")

        logger.info(
            "Aggregation completed: %d channels, %d 15min rows, %d hourly rows.",
            len(loaded_channels),
            len(data_15min),
            len(data_hourly),
        )

        availability = build_candidate_availability(
            data_hourly,
            quality_hourly,
            max_gap_intervals=self.data_config.max_availability_gap_hours,
        )

        df_to_csv(availability, self.project_config.selection_output_dir, "candidate_availability")

        logger.info("Candidate availability: %d usable spans.", len(availability))

        selection, decisions = build_candidate_selection(
            availability,
            channel_registry_df,
            min_valid_duration_days=self.data_config.min_mains_valid_duration_days,
            min_coverage_share=self.data_config.min_mains_coverage_share,
        )

        df_to_csv(selection, self.project_config.selection_output_dir, "candidate_selection")
        df_to_csv(decisions, self.project_config.selection_output_dir, "candidate_selection_decisions")

        logger.info("Candidate selection completed: selected=%s.", selection["candidate_id"].tolist() if not selection.empty else [])

        winners = decisions.loc[decisions["selected"]]

        if winners.empty:
            raise ValueError("No candidate selected. See candidate_selection_decisions.csv.")

        winner = winners.iloc[0]
        meter_key = str(winner["meter_key"])
        column_name = f"{meter_key}_power_w"

        canonical_manifest = pd.DataFrame(
            [
                {
                    "candidate_id": winner["candidate_id"],
                    "house": int(winner["house"]),
                    "meter_key": meter_key,
                    "column_name": column_name,
                    "window_start": winner["window_start"],
                    "window_end": winner["window_end"],
                }
            ]
        )

        window_start = pd.to_datetime(winner["window_start"], utc=True)
        window_end = pd.to_datetime(winner["window_end"], utc=True)

        quality_columns = [
            f"{meter_key}_valid_observation_count",
            f"{meter_key}_coverage_share",
            f"{meter_key}_coverage_mask",
        ]
        quality_rename = {column: column.replace(meter_key, column_name, 1) for column in quality_columns}

        canonical_data_15min = data_15min.loc[window_start:window_end, [meter_key]].rename(columns={meter_key: column_name})
        canonical_data_hourly = data_hourly.loc[window_start:window_end, [meter_key]].rename(columns={meter_key: column_name})
        canonical_quality_15min = quality_15min.loc[window_start:window_end, quality_columns].rename(columns=quality_rename)
        canonical_quality_hourly = quality_hourly.loc[window_start:window_end, quality_columns].rename(columns=quality_rename)

        df_to_csv(
            canonical_manifest,
            self.project_config.canonical_output_dir,
            "canonical_manifest",
        )
        df_to_csv(
            canonical_data_15min.reset_index(),
            self.project_config.canonical_output_dir,
            "canonical_data_15min",
        )
        df_to_csv(
            canonical_data_hourly.reset_index(),
            self.project_config.canonical_output_dir,
            "canonical_data_hourly",
        )
        df_to_csv(
            canonical_quality_15min.reset_index(),
            self.project_config.canonical_output_dir,
            "canonical_quality_15min",
        )
        df_to_csv(
            canonical_quality_hourly.reset_index(),
            self.project_config.canonical_output_dir,
            "canonical_quality_hourly",
        )

        logger.info("Data preparation completed successfully. Canonical candidate: %s.", winner["candidate_id"])


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    DataPreparationRunner().run()


if __name__ == "__main__":
    main()

