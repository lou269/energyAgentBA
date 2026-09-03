# python -m src.forecasting.forecasting_runner
# python -m src.forecasting.forecasting_runner --split test

from __future__ import annotations

import argparse
from dataclasses import asdict
import logging
from datetime import UTC, datetime
from typing import Literal, cast

import pandas as pd

from src.pipeline.io import df_to_csv
from src.config.forecasting_config import ForecastingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.forecasting.evaluation import evaluate_forecasts, select_primary_naive_reference
from src.forecasting.walk_forward import ProphetVariantParameters, build_walk_forward_forecasts

logger = logging.getLogger(__name__)

EvaluationSplit = Literal["validation", "test"]


class ForecastingRunner:
    """Orchestriert Forecast-Erzeugung, Evaluation und Speicherung."""

    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        forecasting_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.forecasting_config = forecasting_config or ForecastingConfig()

    def run(self, split: EvaluationSplit = "validation") -> None:
        ensure_project_directories(self.project_config)

        if (
            split == "test"
            and self.forecasting_config.primary_naive_reference
            not in self.forecasting_config.baseline_model_ids
        ):
            raise ValueError(
                "primary_naive_reference must be one of the configured naive baselines before running the test split."
            )

        logger.info("Starting forecasting for split %s...", split)

        treated_hourly = pd.read_csv(
            self.project_config.preprocessing_output_dir / "treated_hourly.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        imputation_mask_hourly = pd.read_csv(
            self.project_config.preprocessing_output_dir / "imputation_mask_hourly.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        split_manifest = pd.read_csv(
            self.project_config.preprocessing_output_dir / "split_manifest.csv",
            parse_dates=["start", "end"],
        )

        canonical_manifest = pd.read_csv(
            self.project_config.canonical_output_dir / "canonical_manifest.csv"
        )

        mains_targets = canonical_manifest.loc[
            canonical_manifest["channel_role"].eq("mains"),
            ["candidate_id", "meter_key"],
        ].drop_duplicates()

        if len(mains_targets) != 1:
            raise ValueError("Canonical manifest must contain exactly one mains target.")

        target_column = str(mains_targets.iloc[0]["meter_key"])

        hourly_splits = split_manifest.loc[
            split_manifest["frequency"].eq("hourly")
        ].set_index("split")

        split_start = hourly_splits.loc[split, "start"]
        split_end = hourly_splits.loc[split, "end"]

        fixed_history = treated_hourly.loc[
            treated_hourly.index < split_start,
            target_column,
        ]

        evaluation_targets = treated_hourly.loc[
            split_start:split_end,
            target_column,
        ]

        evaluation_imputation_mask = imputation_mask_hourly.loc[
            split_start:split_end,
            target_column,
        ]

        run_id = (
            f"{split}_"
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )

        prophet_variant = cast(
            ProphetVariantParameters,
            asdict(self.forecasting_config.selected_prophet_variant),
        )

        prophet_variants = (prophet_variant,)
        forecasts = build_walk_forward_forecasts(
            fixed_history=fixed_history,
            evaluation_targets=evaluation_targets,
            evaluation_imputation_mask=evaluation_imputation_mask,
            run_id=run_id,
            experiment_id=self.forecasting_config.experiment_id,
            split=split,
            horizon_hours=self.forecasting_config.horizon_hours,
            forecast_origin_step_hours=self.forecasting_config.forecast_origin_step_hours,
            baseline_model_ids=self.forecasting_config.baseline_model_ids,
            prophet_variants=prophet_variants,
            growth=self.forecasting_config.growth,
            daily_seasonality=self.forecasting_config.daily_seasonality,
            yearly_seasonality=self.forecasting_config.yearly_seasonality,
            interval_width=self.forecasting_config.interval_width,
            uncertainty_samples=self.forecasting_config.uncertainty_samples,
            clip_negative_forecasts=(
                self.forecasting_config.negative_forecast_handling == "clip_zero"
            ),
            config_version=self.forecasting_config.config_version,
        )

        evaluation_results = evaluate_forecasts(
            forecasts,
            horizon_hours=self.forecasting_config.horizon_hours,
            comparison_model_ids=(self.forecasting_config.selected_prophet_variant.model_id,),
            reference_model_ids=self.forecasting_config.baseline_model_ids,
            nominal_interval_level=self.forecasting_config.interval_width,
        )

        if split == "validation":
            primary_naive_reference = select_primary_naive_reference(
                evaluation_results["overall_metrics"],
                self.forecasting_config.baseline_model_ids,
            )

            df_to_csv(
                pd.DataFrame({"model_id": [primary_naive_reference]}),
                self.project_config.forecasting_output_dir,
                "primary_naive_reference_validation",
            )
        else:
            primary_naive_reference = self.forecasting_config.primary_naive_reference

        df_to_csv(
            forecasts,
            self.project_config.forecasting_output_dir,
            f"forecasts_{split}",
        )

        for name, result in evaluation_results.items():
            df_to_csv(
                result,
                self.project_config.forecasting_output_dir,
                f"{name}_{split}",
            )

        logger.info(
            "Forecasting completed: split=%s, origins=%d, primary naive reference=%s.",
            split,
            forecasts["forecast_origin"].nunique(),
            primary_naive_reference,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split",
        choices=("validation", "test"),
        default="validation",
    )
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    ForecastingRunner().run(
        split=cast(EvaluationSplit, arguments.split)
    )


if __name__ == "__main__":
    main()
