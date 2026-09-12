# conda activate nilmtk-env
# python -m experiments.component_studies.k1_preprocessing.k1_data_preparation_runner

from __future__ import annotations

import logging

import pandas as pd
from nilmtk import DataSet

from src.common.channel_tables import load_channel_tables, mains_channels
from src.common.column_naming import channel_data_column
from src.config.config_nilmtk import DataPreparationConfig
from src.config.project_config import ProjectConfig
from src.data_preparation.aggregation.aggregation import build_aggregated_data
from src.data_preparation.aggregation.channel_loading import build_loaded_channels
from src.data_preparation.selection.candidate_availability import build_candidate_availability
from src.pipeline.io import df_to_csv

from experiments.component_studies.k1_preprocessing.k1_config import (
    FIXED_VALIDATION_END,
    FIXED_VALIDATION_START,
    K1_VARIANTS,
    k1_variant_output_dir,
)

logger = logging.getLogger(__name__)


def run() -> None:
    project_config = ProjectConfig()
    data_config = DataPreparationConfig()

    dataset = DataSet(project_config.dataset_path)

    channel_registry_df, channel_quality_df = load_channel_tables(project_config)

    logger.info("Loading channels from dataset (shared across all K1 variants)...")

    loaded_channels = build_loaded_channels(
        dataset=dataset,
        channel_quality=channel_quality_df,
        canonical_ac_type=data_config.canonical_ac_type,
        mains_only=True,
        selected_house_ids=data_config.selected_house_ids,
    )

    sample_periods = dict(zip(channel_registry_df["meter_key"], channel_registry_df["sample_period_seconds"]))

    _, _, data_hourly, quality_hourly = build_aggregated_data(
        channels=loaded_channels,
        sample_periods=sample_periods,
        min_coverage_share=data_config.min_coverage_share,
    )

    for variant in K1_VARIANTS:
        logger.info(
            "Variant %s: building candidate window with max_availability_gap_hours=%d...",
            variant.variant_id,
            variant.max_availability_gap_hours,
        )

        availability = build_candidate_availability(
            data_hourly,
            quality_hourly,
            max_gap_intervals=variant.max_availability_gap_hours,
        )

        candidates = availability.merge(
            mains_channels(channel_registry_df),
            on="meter_key",
            how="inner",
        )
        candidates["start"] = pd.to_datetime(candidates["start"], utc=True)
        candidates["end"] = pd.to_datetime(candidates["end"], utc=True)

        # nicht laengster Abschnitt, sondern der der das fixe Validation-Fenster enthaelt --
        # sonst vergleichen die Varianten auf verschiedenen Kalenderzeitraeumen
        containing = candidates.loc[
            candidates["start"].le(FIXED_VALIDATION_START)
            & candidates["end"].ge(FIXED_VALIDATION_END)
            & candidates["coverage_share"].ge(data_config.min_mains_coverage_share)
        ]

        if containing.empty:
            raise ValueError(
                f"No span contains the fixed validation window for variant {variant.variant_id}. See candidate_availability table."
            )

        winner = containing.sort_values("length_days", ascending=False).iloc[0]
        meter_key = str(winner["meter_key"])
        candidate_id = f"H{int(winner['house'])}-M{int(winner['meter_instance'])}-fixedwindow"

        window_start = winner["start"]
        window_end = FIXED_VALIDATION_END

        quality_columns = [
            f"{meter_key}_valid_observation_count",
            f"{meter_key}_coverage_share",
            f"{meter_key}_coverage_mask",
        ]

        canonical_data_hourly = data_hourly.loc[window_start:window_end, [meter_key]].rename(
            columns={meter_key: channel_data_column(meter_key, "hourly")}
        )
        canonical_quality_hourly = quality_hourly.loc[window_start:window_end, quality_columns]

        length_days = (window_end - window_start) / pd.Timedelta(days=1)
        train_length_days = (FIXED_VALIDATION_START - window_start) / pd.Timedelta(days=1)

        canonical_manifest = pd.DataFrame(
            [
                {
                    "candidate_id": candidate_id,
                    "house": int(winner["house"]),
                    "meter_key": meter_key,
                    "window_start": window_start,
                    "window_end": window_end,
                    "length_days": length_days,
                    "train_length_days": train_length_days,
                    "max_availability_gap_hours": variant.max_availability_gap_hours,
                }
            ]
        )

        selection_dir = k1_variant_output_dir(variant.variant_id) / "selection"
        canonical_dir = k1_variant_output_dir(variant.variant_id) / "canonical"
        selection_dir.mkdir(parents=True, exist_ok=True)
        canonical_dir.mkdir(parents=True, exist_ok=True)

        df_to_csv(availability, selection_dir, "candidate_availability")
        df_to_csv(canonical_manifest, canonical_dir, "canonical_manifest")
        df_to_csv(canonical_data_hourly.reset_index(), canonical_dir, "canonical_data_hourly")
        df_to_csv(canonical_quality_hourly.reset_index(), canonical_dir, "canonical_quality_hourly")

        logger.info(
            "Variant %s: candidate=%s, window=%s..%s, train_length_days=%.1f",
            variant.variant_id,
            candidate_id,
            window_start,
            window_end,
            train_length_days,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()

