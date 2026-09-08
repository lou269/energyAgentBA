# python -m src.preprocessing.preprocessing_runner

from __future__ import annotations

import logging

import pandas as pd

from src.pipeline.io import df_to_csv
from src.config.preprocessing_config import PreprocessingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.preprocessing.gap_treatment import build_gap_treated_data
from src.preprocessing.plausibility_check import build_plausibility_flags
from src.preprocessing.split import build_chronological_split


logger = logging.getLogger(__name__)


class PreprocessingRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        preprocessing_config: PreprocessingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.preprocessing_config = preprocessing_config or PreprocessingConfig()

    def _read_canonical(self, name: str) -> pd.DataFrame:
        return pd.read_csv(
            self.project_config.canonical_output_dir / f"{name}.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        logger.info("Starting preprocessing pipeline...")

        data_15min = self._read_canonical("canonical_data_15min")
        quality_15min = self._read_canonical("canonical_quality_15min")
        data_hourly = self._read_canonical("canonical_data_hourly")
        quality_hourly = self._read_canonical("canonical_quality_hourly")

        logger.info("Checking value plausibility...")

        plausibility_15min = build_plausibility_flags(
            data_15min,
            quality_15min,
            stuck_value_min_hours=self.preprocessing_config.stuck_value_min_hours,
            sample_period_hours=0.25,
        )

        plausibility_hourly = build_plausibility_flags(
            data_hourly,
            quality_hourly,
            stuck_value_min_hours=self.preprocessing_config.stuck_value_min_hours,
            sample_period_hours=1.0,
        )

        logger.info("Building chronological splits...")

        (
            train_15min,
            train_quality_15min,
            validation_15min,
            validation_quality_15min,
            test_15min,
            test_quality_15min,
        ) = build_chronological_split(
            data_15min,
            quality_15min,
            train_share=self.preprocessing_config.train_share,
            validation_share=self.preprocessing_config.validation_share,
        )

        (
            train_hourly,
            train_quality_hourly,
            validation_hourly,
            validation_quality_hourly,
            test_hourly,
            test_quality_hourly,
        ) = build_chronological_split(
            data_hourly,
            quality_hourly,
            train_share=self.preprocessing_config.train_share,
            validation_share=self.preprocessing_config.validation_share,
        )

        split_manifest = pd.DataFrame(
            [
                {
                    "frequency": "15min",
                    "split": "train",
                    "start": train_15min.index.min(),
                    "end": train_15min.index.max(),
                    "row_count": len(train_15min),
                },
                {
                    "frequency": "15min",
                    "split": "validation",
                    "start": validation_15min.index.min(),
                    "end": validation_15min.index.max(),
                    "row_count": len(validation_15min),
                },
                {
                    "frequency": "15min",
                    "split": "test",
                    "start": test_15min.index.min(),
                    "end": test_15min.index.max(),
                    "row_count": len(test_15min),
                },
                {
                    "frequency": "hourly",
                    "split": "train",
                    "start": train_hourly.index.min(),
                    "end": train_hourly.index.max(),
                    "row_count": len(train_hourly),
                },
                {
                    "frequency": "hourly",
                    "split": "validation",
                    "start": validation_hourly.index.min(),
                    "end": validation_hourly.index.max(),
                    "row_count": len(validation_hourly),
                },
                {
                    "frequency": "hourly",
                    "split": "test",
                    "start": test_hourly.index.min(),
                    "end": test_hourly.index.max(),
                    "row_count": len(test_hourly),
                },
            ]
        )

        df_to_csv(
            split_manifest,
            self.project_config.preprocessing_output_dir,
            "split_manifest",
        )

        logger.info(
            "Chronological split completed: %d/%d/%d 15-minute rows, %d/%d/%d hourly rows.",
            len(train_15min),
            len(validation_15min),
            len(test_15min),
            len(train_hourly),
            len(validation_hourly),
            len(test_hourly),
        )

        logger.info("Applying causal gap treatment...")

        (
            train_treated_15min,
            train_imputation_mask_15min,
            validation_treated_15min,
            validation_imputation_mask_15min,
            test_treated_15min,
            test_imputation_mask_15min,
        ) = build_gap_treated_data(
            train_15min,
            train_quality_15min,
            validation_15min,
            validation_quality_15min,
            test_15min,
            test_quality_15min,
            max_gap_intervals=self.preprocessing_config.max_imputation_gap_15min,
        )

        (
            train_treated_hourly,
            train_imputation_mask_hourly,
            validation_treated_hourly,
            validation_imputation_mask_hourly,
            test_treated_hourly,
            test_imputation_mask_hourly,
        ) = build_gap_treated_data(
            train_hourly,
            train_quality_hourly,
            validation_hourly,
            validation_quality_hourly,
            test_hourly,
            test_quality_hourly,
            max_gap_intervals=self.preprocessing_config.max_imputation_gap_hourly
        )

        treated_15min = pd.concat(
            [
                train_treated_15min,
                validation_treated_15min,
                test_treated_15min,
            ]
        )

        imputation_mask_15min = pd.concat(
            [
                train_imputation_mask_15min,
                validation_imputation_mask_15min,
                test_imputation_mask_15min,
            ]
        )

        treated_hourly = pd.concat(
            [
                train_treated_hourly,
                validation_treated_hourly,
                test_treated_hourly,
            ]
        )

        imputation_mask_hourly = pd.concat(
            [
                train_imputation_mask_hourly,
                validation_imputation_mask_hourly,
                test_imputation_mask_hourly,
            ]
        )

        preprocessing_outputs = {
            "treated_15min": treated_15min,
            "imputation_mask_15min": imputation_mask_15min,
            "treated_hourly": treated_hourly,
            "imputation_mask_hourly": imputation_mask_hourly,
            "plausibility_15min": plausibility_15min,
            "plausibility_hourly": plausibility_hourly,
        }

        for name, frame in preprocessing_outputs.items():
            df_to_csv(
                frame.reset_index(),
                self.project_config.preprocessing_output_dir,
                name,
            )

        logger.info("Preprocessing completed successfully: %d output artifacts.", len(preprocessing_outputs) + 1)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    PreprocessingRunner().run()


if __name__ == "__main__":
    main()