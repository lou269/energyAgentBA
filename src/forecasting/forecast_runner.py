# python -m src.forecasting.forecast_runner
# python -m src.forecasting.forecast_runner --split test

import argparse
from dataclasses import asdict, dataclass
import logging
from time import perf_counter
from typing import Literal, cast

import numpy as np
import pandas as pd

from src.common.column_naming import imputation_column, treated_column
from src.pipeline.io import df_to_csv, next_sequential_number, save_json
from src.config.config_forecasting import ForecastingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.forecasting.evaluation import evaluate_forecasts, select_primary_naive_reference
from src.forecasting.forecast_run_manifest import build_forecast_run_manifest
from docs.plots.plot_forecast_ergebnis import build_forecast_plot

from src.forecasting.walk_forward import ProphetVariantParameters, build_walk_forward_forecasts

logger = logging.getLogger(__name__)

EvaluationSplit = Literal["validation", "test"]


@dataclass(frozen=True)
class ForecastingResult:
    forecasts: pd.DataFrame
    evaluation_results: dict[str, pd.DataFrame]
    primary_naive_reference: str
    split_start: pd.Timestamp
    split_end: pd.Timestamp
    fixed_history_start: pd.Timestamp
    fixed_history_end: pd.Timestamp


def run_forecasting(
    treated_hourly: pd.DataFrame,
    imputation_mask_hourly: pd.DataFrame,
    split_manifest: pd.DataFrame,
    target_column: str,
    meter_key: str,
    split: EvaluationSplit,
    run_id: str,
    config: ForecastingConfig,
    local_timezone: str,
) -> ForecastingResult:
    if (
        split == "test"
        and config.primary_naive_reference not in config.baseline_model_ids
    ):
        raise ValueError("primary_naive_reference must be one of the configured naive baselines before running the test split.")

    hourly_splits = split_manifest.loc[
        split_manifest["frequency"].eq("hourly")
    ].set_index("split")

    split_start = hourly_splits.loc[split, "start"]
    split_end = hourly_splits.loc[split, "end"]

    fixed_history = treated_hourly.loc[treated_hourly.index < split_start, target_column]

    evaluation_targets = treated_hourly.loc[split_start:split_end, target_column]

    evaluation_imputation_mask = imputation_mask_hourly.loc[split_start:split_end, imputation_column(meter_key)]

    prophet_variant = cast(ProphetVariantParameters, asdict(config.selected_prophet_variant))

    prophet_variants = (prophet_variant,)
    forecasts = build_walk_forward_forecasts(
        fixed_history=fixed_history,
        evaluation_targets=evaluation_targets,
        evaluation_imputation_mask=evaluation_imputation_mask,
        run_id=run_id,
        experiment_id=config.experiment_id,
        split=split,
        horizon_hours=config.horizon_hours,
        forecast_origin_step_hours=config.forecast_origin_step_hours,
        frequency=config.frequency,
        baseline_model_ids=config.baseline_model_ids,
        prophet_variants=prophet_variants,
        growth=config.growth,
        daily_seasonality=config.daily_seasonality,
        country_holidays=config.country_holidays,
        local_timezone=local_timezone,
        log_transform=config.log_transform,
        interval_width=config.interval_width,
        uncertainty_samples=config.uncertainty_samples,
        clip_negative_forecasts=config.negative_forecast_handling == "clip_zero",
        config_version=config.config_version,
    )

    evaluation_results = evaluate_forecasts(
        forecasts,
        horizon_hours=config.horizon_hours,
        comparison_model_ids=(config.selected_prophet_variant.model_id,),
        reference_model_ids=config.baseline_model_ids,
        nominal_interval_level=config.interval_width,
        mape_min_eligible_watts=config.mape_min_eligible_watts,
    )

    if split == "validation":
        primary_naive_reference = select_primary_naive_reference(
            evaluation_results["overall_metrics"],
            config.baseline_model_ids,
        )
    else:
        primary_naive_reference = config.primary_naive_reference

    return ForecastingResult(
        forecasts=forecasts,
        evaluation_results=evaluation_results,
        primary_naive_reference=cast(str, primary_naive_reference),
        split_start=cast(pd.Timestamp, split_start),
        split_end=cast(pd.Timestamp, split_end),
        fixed_history_start=fixed_history.index[0],
        fixed_history_end=fixed_history.index[-1],
    )


class ForecastingRunner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        forecasting_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.forecasting_config = forecasting_config or ForecastingConfig()

    def run(self, split: EvaluationSplit = "validation") -> None:
        ensure_project_directories(self.project_config)
        np.random.seed(self.forecasting_config.seed)
        run_started = perf_counter()

        logger.info("Starting forecasting for split %s...", split)

        treated_path = self.project_config.preprocessing_output_dir / "treated_hourly.csv"
        mask_path = self.project_config.preprocessing_output_dir / "imputation_mask_hourly.csv"
        split_manifest_path = self.project_config.preprocessing_output_dir / "split_manifest.csv"
        canonical_manifest_path = self.project_config.canonical_output_dir / "canonical_manifest.csv"

        treated_hourly = pd.read_csv(
            treated_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        imputation_mask_hourly = pd.read_csv(
            mask_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        split_manifest = pd.read_csv(
            split_manifest_path,
            parse_dates=["start", "end"],
        )

        canonical_manifest = pd.read_csv(canonical_manifest_path)

        if len(canonical_manifest) != 1:
            raise ValueError("Canonical manifest must contain exactly one mains target.")

        candidate_id = str(canonical_manifest.iloc[0]["candidate_id"])
        meter_key = str(canonical_manifest.iloc[0]["meter_key"])
        target_column = treated_column(meter_key)

        split_abbreviation = "val" if split == "validation" else split
        run_number = next_sequential_number(self.project_config.forecasting_output_dir, prefix=f"fc_{split_abbreviation}")
        run_id = f"{split}_{run_number:03d}"

        run_directory = self.project_config.forecasting_output_dir / f"fc_{split_abbreviation}_{run_number:03d}"

        if run_directory.exists():
            raise FileExistsError(f"Forecasting run directory already exists: {run_directory}")

        run_directory.mkdir(parents=True, exist_ok=False)

        result = run_forecasting(
            treated_hourly=treated_hourly,
            imputation_mask_hourly=imputation_mask_hourly,
            split_manifest=split_manifest,
            target_column=target_column,
            meter_key=meter_key,
            split=split,
            run_id=run_id,
            config=self.forecasting_config,
            local_timezone=self.project_config.timezone,
        )

        forecasts = result.forecasts
        evaluation_results = result.evaluation_results
        primary_naive_reference = result.primary_naive_reference
        split_start = result.split_start
        split_end = result.split_end

        if split == "validation":
            df_to_csv(
                pd.DataFrame({"model_id": [primary_naive_reference]}),
                run_directory,
                "primary_naive_reference_validation",
            )

        df_to_csv(
            forecasts,
            run_directory,
            f"forecasts_{split}"
        )

        for name, evaluation_result in evaluation_results.items():
            df_to_csv(
                evaluation_result,
                run_directory,
                f"{name}_{split}"
            )

        output_paths = {
            "forecasts": run_directory / f"forecasts_{split}.csv",
            **{
                name: run_directory / f"{name}_{split}.csv"
                for name in evaluation_results
            },
        }

        if split == "validation":
            output_paths["primary_naive_reference"] = run_directory / "primary_naive_reference_validation.csv"

        manifest = build_forecast_run_manifest(
            project_root=self.project_config.project_root,
            run_id=run_id,
            experiment_id=self.forecasting_config.experiment_id,
            split=split,
            candidate_id=candidate_id,
            config_values=asdict(self.forecasting_config),
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
                "fixed_history_start": result.fixed_history_start,
                "fixed_history_end": result.fixed_history_end,
                "first_forecast_origin": forecasts["forecast_origin"].min(),
            },
            forecast_origins=tuple(forecasts["forecast_origin"].drop_duplicates().sort_values()),
            model_parameters={
                "growth": self.forecasting_config.growth,
                "daily_seasonality": self.forecasting_config.daily_seasonality,
                "country_holidays": self.forecasting_config.country_holidays,
                "local_timezone": self.project_config.timezone,
                "log_transform": self.forecasting_config.log_transform,
                "interval_width": self.forecasting_config.interval_width,
                "variant": asdict(self.forecasting_config.selected_prophet_variant),
            },
            seasonalities={
                self.forecasting_config.selected_prophet_variant.model_id: {
                    "daily": self.forecasting_config.daily_seasonality,
                    "weekly": self.forecasting_config.selected_prophet_variant.weekly_seasonality,
                    "yearly": self.forecasting_config.selected_prophet_variant.yearly_seasonality,
                    "holidays": self.forecasting_config.country_holidays,
                    "local_timezone": self.project_config.timezone,
                    "log_transform": self.forecasting_config.log_transform,
                }
            },
            history_rules={
                self.forecasting_config.selected_prophet_variant.model_id: {
                    "history_mode": self.forecasting_config.selected_prophet_variant.history_mode,
                    "rolling_window_hours": self.forecasting_config.selected_prophet_variant.rolling_window_hours,
                    "retraining_interval_hours": self.forecasting_config.selected_prophet_variant.retraining_interval_hours,
                }
            },
            metric_definitions={
                "metrics": ["mae", "rmse", "mape"],
                "primary_metric": "mae",
                "mape_positive_targets_only": True,
            },
            exclusion_rules={
                "exclude_imputed_targets": True,
                "complete_horizons_only": True,
            },
            primary_naive_reference=primary_naive_reference,
            seed=self.forecasting_config.seed,
            uncertainty_samples=self.forecasting_config.uncertainty_samples,
            runtime_seconds=perf_counter() - run_started,
        )

        save_json(
            manifest,
            run_directory / f"run_manifest_{split}.json",
        )

        build_forecast_plot(
            run_directory,
            run_directory,
            split=split,
            active_model_id=self.forecasting_config.selected_prophet_variant.model_id,
            baseline_model_ids=self.forecasting_config.baseline_model_ids,
            reference_baseline=cast(str, primary_naive_reference),
        )

        logger.info(
            "Forecasting completed: split=%s, origins=%d, primary naive reference=%s.",
            split,
            forecasts["forecast_origin"].nunique(),
            primary_naive_reference,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    arguments = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    ForecastingRunner().run(split=cast(EvaluationSplit, arguments.split))


if __name__ == "__main__":
    main()