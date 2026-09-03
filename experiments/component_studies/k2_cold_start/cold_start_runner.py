# conda activate forecasting-env
# python -m experiments.component_studies.k2_cold_start.cold_start_runner

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import cast

import numpy as np
import pandas as pd

from experiments.component_studies.k2_cold_start.cold_start_config import ColdStartExperimentConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.forecasting.evaluation import evaluate_forecasts, select_primary_naive_reference
from src.forecasting.forecast_run_manifest import build_forecast_run_manifest
from src.forecasting.walk_forward import ProphetVariantParameters, build_walk_forward_forecasts
from src.pipeline.io import df_to_csv

logger = logging.getLogger(__name__)


class ColdStartRunner:

    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        experiment_config: ColdStartExperimentConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.experiment_config = experiment_config or ColdStartExperimentConfig()

    def run(self) -> None:
        np.random.seed(self.experiment_config.seed)
        ensure_project_directories(self.project_config)

        split = self.experiment_config.split

        if (
            split == "test"
            and self.experiment_config.primary_naive_reference
            not in self.experiment_config.baseline_model_ids
        ):
            raise ValueError(
                "primary_naive_reference must be one of the configured naive baselines before running the test split."
            )

        logger.info("Starting cold-start experiment: split=%s", split)
        run_started = perf_counter()

        treated_path = self.project_config.preprocessing_output_dir / "treated_hourly.csv"
        mask_path = self.project_config.preprocessing_output_dir / "imputation_mask_hourly.csv"
        split_manifest_path = self.project_config.preprocessing_output_dir / "split_manifest.csv"
        canonical_manifest_path = self.project_config.canonical_output_dir / "canonical_manifest.csv"

        treated_hourly = pd.read_csv(
            treated_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )
        
        imputation_mask = pd.read_csv(
            mask_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )
        
        split_manifest = pd.read_csv(
            split_manifest_path,
            parse_dates=["start", "end"],
        )
        
        canonical_manifest = pd.read_csv(canonical_manifest_path)

        mains_targets = canonical_manifest.loc[
            canonical_manifest["channel_role"].eq("mains"),
            ["candidate_id", "meter_key"],
        ].drop_duplicates()

        if len(mains_targets) != 1:
            raise ValueError("Canonical manifest must contain exactly one mains target.")

        candidate_id = str(mains_targets.iloc[0]["candidate_id"])
        target_column = str(mains_targets.iloc[0]["meter_key"])

        hourly_splits = split_manifest.loc[
            split_manifest["frequency"].eq("hourly")
        ].set_index("split")

        split_start = hourly_splits.at[split, "start"]
        split_end = hourly_splits.at[split, "end"]

        if not isinstance(split_start, pd.Timestamp) or not isinstance(
            split_end,
            pd.Timestamp,
        ):
            raise TypeError("Split boundaries must be timestamps.")

        # Standardfall: sieben Tage direkt vor dem Evaluation-Split.
        initial_start = (
            pd.Timestamp(self.experiment_config.data_start)
            if self.experiment_config.data_start is not None
            else split_start - pd.Timedelta(hours=self.experiment_config.initial_history_hours)
        )

        first_origin = initial_start + pd.Timedelta(hours=self.experiment_config.initial_history_hours)

        evaluation_end = (
            pd.Timestamp(self.experiment_config.data_end)
            if self.experiment_config.data_end is not None
            else split_end
        )

        if first_origin < split_start or evaluation_end > split_end:
            raise ValueError("Cold-start evaluation must remain inside the selected split.")

        expected_initial_index = pd.date_range(
            start=initial_start,
            periods=self.experiment_config.initial_history_hours,
            freq="1h",
        )

        fixed_history = treated_hourly[target_column].reindex(expected_initial_index)

        if not fixed_history.index.equals(expected_initial_index):
            raise ValueError("Initial history does not use the expected hourly index.")

        evaluation_targets = treated_hourly.loc[
            first_origin:evaluation_end,
            target_column,
        ]

        evaluation_imputation_mask = imputation_mask.loc[
            first_origin:evaluation_end,
            target_column,
        ]

        prophet_variants = tuple(
            cast(ProphetVariantParameters, asdict(variant))
            for variant in self.experiment_config.prophet_variants
        )

        run_id = (
            f"{self.experiment_config.experiment_id}_"
            f"{split}_"
            f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )

        forecasts = build_walk_forward_forecasts(
            fixed_history=fixed_history,
            evaluation_targets=evaluation_targets,
            evaluation_imputation_mask=evaluation_imputation_mask,
            run_id=run_id,
            experiment_id=self.experiment_config.experiment_id,
            split=split,
            horizon_hours=self.experiment_config.horizon_hours,
            forecast_origin_step_hours=self.experiment_config.forecast_origin_step_hours,
            baseline_model_ids=self.experiment_config.baseline_model_ids,
            prophet_variants=prophet_variants,
            growth=self.experiment_config.growth,
            daily_seasonality=self.experiment_config.daily_seasonality,
            yearly_seasonality=self.experiment_config.yearly_seasonality,
            interval_width=self.experiment_config.interval_width,
            uncertainty_samples=self.experiment_config.uncertainty_samples,
            clip_negative_forecasts=(
                self.experiment_config.negative_forecast_handling == "clip_zero"
            ),
            config_version=self.experiment_config.config_version,
            initial_history_hours=self.experiment_config.initial_history_hours,
        )

        prophet_model_ids = tuple(
            variant["model_id"]
            for variant in prophet_variants
        )

        evaluation_results = evaluate_forecasts(
            forecasts,
            horizon_hours=self.experiment_config.horizon_hours,
            comparison_model_ids=prophet_model_ids,
            reference_model_ids=(
                *self.experiment_config.baseline_model_ids,
                "C1",
            ),
            nominal_interval_level=self.experiment_config.interval_width,
        )

        if split == "validation":
            primary_naive_reference = select_primary_naive_reference(
                evaluation_results["overall_metrics"],
                self.experiment_config.baseline_model_ids,
            )
        else:
            primary_naive_reference = self.experiment_config.primary_naive_reference

        run_dir = self.project_config.forecasting_output_dir / self.experiment_config.output_subdir / run_id
        
        run_dir.mkdir(parents=True, exist_ok=False)

        df_to_csv(
            forecasts,
            run_dir,
            "forecasts",
        )

        for name, result in evaluation_results.items():
            df_to_csv(
                result,
                run_dir,
                name,
            )

        df_to_csv(
            pd.DataFrame(
                {"model_id": [primary_naive_reference]}
            ),
            run_dir,
            "primary_naive_reference",
        )

        output_paths = {
            "forecasts": run_dir / "forecasts.csv",
            "primary_naive_reference": run_dir / "primary_naive_reference.csv",
            **{
                name: run_dir / f"{name}.csv"
                for name in evaluation_results
            },
        }

        runtime_seconds = perf_counter() - run_started

        manifest = build_forecast_run_manifest(
            project_root=self.project_config.project_root,
            run_id=run_id,
            experiment_id=self.experiment_config.experiment_id,
            split=split,
            candidate_id=candidate_id,
            config_values=asdict(self.experiment_config),
            source_paths=(
                Path(__file__),
                self.project_config.project_root / "experiments/component_studies/k2_cold_start/cold_start_config.py",
                self.project_config.project_root / "src/forecasting/walk_forward.py",
                self.project_config.project_root / "src/forecasting/prophet_model.py",
                self.project_config.project_root / "src/forecasting/baselines.py",
                self.project_config.project_root / "src/forecasting/evaluation.py",
                self.project_config.project_root / "src/forecasting/schema.py",
            ),
            input_paths={
                "treated_hourly": treated_path,
                "imputation_mask_hourly": mask_path,
                "split_manifest": split_manifest_path,
                "canonical_manifest": canonical_manifest_path,
            },
            output_paths=output_paths,
            split_boundaries={
                "split_start": split_start,
                "split_end": split_end,
                "initial_history_start": fixed_history.index[0],
                "initial_history_end": fixed_history.index[-1],
                "first_forecast_origin": forecasts["forecast_origin"].min(),
                "evaluation_end": evaluation_end,
            },
            forecast_origins=tuple(
                forecasts["forecast_origin"]
                .drop_duplicates()
                .sort_values()
            ),
            model_parameters={
                "growth": self.experiment_config.growth,
                "daily_seasonality": self.experiment_config.daily_seasonality,
                "yearly_seasonality": self.experiment_config.yearly_seasonality,
                "interval_width": self.experiment_config.interval_width,
                "variants": [
                    asdict(variant)
                    for variant
                    in self.experiment_config.prophet_variants
                ],
            },
            seasonalities={
                variant.model_id: {
                    "daily": self.experiment_config.daily_seasonality,
                    "weekly": variant.weekly_seasonality,
                    "yearly": self.experiment_config.yearly_seasonality,
                }
                for variant
                in self.experiment_config.prophet_variants
            },
            history_rules={
                "initial_history_hours": self.experiment_config.initial_history_hours,
                "first_forecast_after_initial_history": True,
                "variants": {
                    variant.model_id: {
                        "history_mode": variant.history_mode,
                        "rolling_window_hours": variant.rolling_window_hours,
                        "retraining_interval_hours": variant.retraining_interval_hours,
                    }
                    for variant
                    in self.experiment_config.prophet_variants
                },
            },
            metric_definitions={
                "metrics": [
                    "mae",
                    "rmse",
                    "mape",
                ],
                "primary_metric": "mae",
                "mape_positive_targets_only": True,
            },
            exclusion_rules={
                "exclude_imputed_targets": True,
                "complete_horizons_only": True,
            },
            primary_naive_reference=primary_naive_reference,
            seed=self.experiment_config.seed,
            uncertainty_samples=self.experiment_config.uncertainty_samples,
            runtime_seconds=runtime_seconds,
        )

        with (run_dir / "run_manifest.json").open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                manifest,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

        logger.info(
            "Cold-start experiment completed: run=%s, origins=%d, "
            "primary naive reference=%s",
            run_id,
            forecasts["forecast_origin"].nunique(),
            primary_naive_reference,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ColdStartRunner().run()


if __name__ == "__main__":
    main()