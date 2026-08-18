# python -m src.preprocessing.preprocessing_runner

from __future__ import annotations

import logging

import joblib
import pandas as pd

from src.analysis.io import df_to_csv
from src.config.data_preparation_config import DataPreparationConfig
from src.config.preprocessing_config import PreprocessingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.preprocessing.aggregation import build_aggregated_data
from src.preprocessing.features import build_features
from src.preprocessing.gap_treatment import build_gap_treated_data
from src.preprocessing.split import build_chronological_split
from src.preprocessing.transformations import apply_transformations, fit_transformations


logger = logging.getLogger(__name__)


class PreprocessingRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        data_preparation_config: DataPreparationConfig | None = None,
        preprocessing_config: PreprocessingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.data_preparation_config = (
            data_preparation_config or DataPreparationConfig()
        )
        self.preprocessing_config = (
            preprocessing_config or PreprocessingConfig()
        )

    def run(self) -> None:
        ensure_project_directories(self.project_config)

        logger.info("Starting preprocessing pipeline...")

        canonical_data = pd.read_csv(
            self.project_config.canonical_output_dir / "canonical_data.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        # 11. Forecast aggregation
        logger.info("Building forecast aggregations...")

        (
            data_15min,
            quality_15min,
            data_hourly,
            quality_hourly,
        ) = build_aggregated_data(
            canonical_data,
            sample_period_seconds=(
                self.data_preparation_config.alignment_sample_period_seconds
            ),
            min_coverage_share=(
                self.preprocessing_config.min_aggregation_coverage_share
            ),
        )

        aggregation_outputs = {
            "aggregated_15min": data_15min,
            "aggregation_quality_15min": quality_15min,
            "aggregated_hourly": data_hourly,
            "aggregation_quality_hourly": quality_hourly,
        }

        for name, frame in aggregation_outputs.items():
            df_to_csv(
                frame.reset_index(),
                self.project_config.preprocessing_output_dir,
                name,
            )

        logger.info(
            "Forecast aggregation completed: %d 15-minute rows, %d hourly rows.",
            len(data_15min),
            len(data_hourly),
        )

        # 12. Chronological train / validation / test split
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
            "Chronological split completed: "
            "%d/%d/%d 15-minute rows, %d/%d/%d hourly rows.",
            len(train_15min),
            len(validation_15min),
            len(test_15min),
            len(train_hourly),
            len(validation_hourly),
            len(test_hourly),
        )

        # 13. Train-only gap treatment
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
            max_gap_intervals=(
                self.preprocessing_config.max_imputation_gap_15min
            ),
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
            max_gap_intervals=(
                self.preprocessing_config.max_imputation_gap_hourly
            ),
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

        gap_outputs = {
            "treated_15min": treated_15min,
            "imputation_mask_15min": imputation_mask_15min,
            "treated_hourly": treated_hourly,
            "imputation_mask_hourly": imputation_mask_hourly,
        }

        for name, frame in gap_outputs.items():
            df_to_csv(
                frame.reset_index(),
                self.project_config.preprocessing_output_dir,
                name,
            )

        logger.info("Causal gap treatment completed.")

        # 14. Causal feature engineering
        logger.info("Building causal features...")

        features_15min = build_features(
            treated_15min,
            imputation_mask_15min,
            lags=self.preprocessing_config.lags_15min,
            rolling_windows=self.preprocessing_config.rolling_windows_15min,
        )

        train_features_15min = features_15min.loc[
            train_treated_15min.index
        ]
        validation_features_15min = features_15min.loc[
            validation_treated_15min.index
        ]
        test_features_15min = features_15min.loc[
            test_treated_15min.index
        ]

        features_hourly = build_features(
            treated_hourly,
            imputation_mask_hourly,
            lags=self.preprocessing_config.lags_hourly,
            rolling_windows=self.preprocessing_config.rolling_windows_hourly,
        )

        train_features_hourly = features_hourly.loc[
            train_treated_hourly.index
        ]
        validation_features_hourly = features_hourly.loc[
            validation_treated_hourly.index
        ]
        test_features_hourly = features_hourly.loc[
            test_treated_hourly.index
        ]

        logger.info("Causal feature engineering completed.")

        # 15. Train-only feature transformations
        logger.info("Applying train-only feature transformations...")

        (
            train_features_15min,
            selector_15min,
            scaler_15min,
            selected_columns_15min,
        ) = fit_transformations(
            train_features_15min,
            variance_threshold=(
                self.preprocessing_config.feature_variance_threshold
            ),
        )

        validation_features_15min = apply_transformations(
            validation_features_15min,
            selector_15min,
            scaler_15min,
            selected_columns_15min,
        )

        test_features_15min = apply_transformations(
            test_features_15min,
            selector_15min,
            scaler_15min,
            selected_columns_15min,
        )

        (
            train_features_hourly,
            selector_hourly,
            scaler_hourly,
            selected_columns_hourly,
        ) = fit_transformations(
            train_features_hourly,
            variance_threshold=(
                self.preprocessing_config.feature_variance_threshold
            ),
        )

        validation_features_hourly = apply_transformations(
            validation_features_hourly,
            selector_hourly,
            scaler_hourly,
            selected_columns_hourly,
        )

        test_features_hourly = apply_transformations(
            test_features_hourly,
            selector_hourly,
            scaler_hourly,
            selected_columns_hourly,
        )

        features_15min = pd.concat(
            [
                train_features_15min,
                validation_features_15min,
                test_features_15min,
            ]
        )

        features_hourly = pd.concat(
            [
                train_features_hourly,
                validation_features_hourly,
                test_features_hourly,
            ]
        )

        df_to_csv(
            features_15min.reset_index(),
            self.project_config.preprocessing_output_dir,
            "features_15min",
        )

        df_to_csv(
            features_hourly.reset_index(),
            self.project_config.preprocessing_output_dir,
            "features_hourly",
        )

        df_to_csv(
            pd.DataFrame({"feature": selected_columns_15min}),
            self.project_config.preprocessing_output_dir,
            "selected_features_15min",
        )

        df_to_csv(
            pd.DataFrame({"feature": selected_columns_hourly}),
            self.project_config.preprocessing_output_dir,
            "selected_features_hourly",
        )

        joblib.dump(
            selector_15min,
            self.project_config.preprocessing_output_dir
            / "selector_15min.joblib",
        )
        joblib.dump(
            scaler_15min,
            self.project_config.preprocessing_output_dir
            / "scaler_15min.joblib",
        )
        joblib.dump(
            selector_hourly,
            self.project_config.preprocessing_output_dir
            / "selector_hourly.joblib",
        )
        joblib.dump(
            scaler_hourly,
            self.project_config.preprocessing_output_dir
            / "scaler_hourly.joblib",
        )

        logger.info(
            "Feature transformations completed: "
            "%d 15-minute features, %d hourly features.",
            len(selected_columns_15min),
            len(selected_columns_hourly),
        )

        logger.info("Preprocessing pipeline completed successfully.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    PreprocessingRunner().run()


if __name__ == "__main__":
    main()