# conda activate forecasting-env
# python -m experiments.component_studies.k2_forecast_model.forecast_model_runner

import logging
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Literal, cast

import numpy as np
import pandas as pd

from experiments.component_studies.k2_forecast_model.forecast_model_config import ForecastModelExperimentConfig
from src.common.column_naming import imputation_column, treated_column
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.forecasting.evaluation import select_primary_naive_reference
from src.forecasting.forecast_run_manifest import build_forecast_run_manifest
from src.forecasting.forecasting import run_forecast_comparison
from src.forecasting.walk_forward import ProphetVariantParameters
from src.pipeline.io import df_to_csv, next_sequential_number, save_json
from docs.plots.plot_forecast_model_vergleich import build_forecast_model_plot

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

ComparisonMode = Literal["rolling", "macro"]


class ForecastModelRunner:

    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        experiment_config: ForecastModelExperimentConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.experiment_config = experiment_config or ForecastModelExperimentConfig()

    def run(self, modes: tuple[ComparisonMode, ...] = ("rolling", "macro")) -> None:
        np.random.seed(self.experiment_config.seed)
        ensure_project_directories(self.project_config)

        split = self.experiment_config.split

        if (
            split == "test"
            and self.experiment_config.primary_naive_reference
            not in self.experiment_config.baseline_model_ids
        ):
            raise ValueError("primary_naive_reference must be one of the configured naive baselines before running the test split.")

        treated_path = self.project_config.preprocessing_output_dir / "treated_hourly.csv"
        mask_path = self.project_config.preprocessing_output_dir / "imputation_mask_hourly.csv"
        split_manifest_path = self.project_config.preprocessing_output_dir / "split_manifest.csv"
        canonical_manifest_path = self.project_config.canonical_output_dir / "canonical_manifest.csv"

        treated_hourly = pd.read_csv(treated_path, parse_dates=["timestamp"], index_col="timestamp")
        imputation_mask = pd.read_csv(mask_path, parse_dates=["timestamp"], index_col="timestamp")
        split_manifest = pd.read_csv(split_manifest_path, parse_dates=["start", "end"])
        canonical_manifest = pd.read_csv(canonical_manifest_path)

        candidate_id = str(canonical_manifest.iloc[0]["candidate_id"])
        meter_key = str(canonical_manifest.iloc[0]["meter_key"])
        target_column = treated_column(meter_key)
        mask_column = imputation_column(meter_key)

        hourly_splits = split_manifest.loc[split_manifest["frequency"].eq("hourly")].set_index("split")

        split_start = hourly_splits.at[split, "start"]
        split_end = hourly_splits.at[split, "end"]

        if not isinstance(split_start, pd.Timestamp) or not isinstance(split_end, pd.Timestamp):
            raise TypeError("Split boundaries must be timestamps.")

        fixed_history = treated_hourly.loc[treated_hourly.index < split_start, target_column]
        evaluation_targets = treated_hourly.loc[split_start:split_end, target_column]
        evaluation_imputation_mask = imputation_mask.loc[split_start:split_end, mask_column]

        candidates: tuple[str | ProphetVariantParameters, ...] = (
            *self.experiment_config.baseline_model_ids,
            *(
                cast(ProphetVariantParameters, asdict(variant))
                for variant in self.experiment_config.prophet_variants
            ),
        )
        prophet_model_ids = tuple(variant.model_id for variant in self.experiment_config.prophet_variants)
        reference_model_ids = self.experiment_config.baseline_model_ids
        if "C1" in prophet_model_ids and "C1" not in reference_model_ids:
            reference_model_ids = (*reference_model_ids, "C1")

        run_number = next_sequential_number(OUTPUT_DIR, prefix="k2")
        run_root = OUTPUT_DIR / f"k2_{run_number:03d}"

        for mode in modes:
            self._run_mode(
                mode,
                split=split,
                candidate_id=candidate_id,
                treated_path=treated_path,
                mask_path=mask_path,
                split_manifest_path=split_manifest_path,
                canonical_manifest_path=canonical_manifest_path,
                split_start=split_start,
                split_end=split_end,
                fixed_history=fixed_history,
                evaluation_targets=evaluation_targets,
                evaluation_imputation_mask=evaluation_imputation_mask,
                candidates=candidates,
                prophet_model_ids=prophet_model_ids,
                reference_model_ids=reference_model_ids,
                run_number=run_number,
                run_root=run_root,
            )

    def _run_mode(
        self,
        mode: ComparisonMode,
        *,
        split: str,
        candidate_id: str,
        treated_path: Path,
        mask_path: Path,
        split_manifest_path: Path,
        canonical_manifest_path: Path,
        split_start: pd.Timestamp,
        split_end: pd.Timestamp,
        fixed_history: pd.Series,
        evaluation_targets: pd.Series,
        evaluation_imputation_mask: pd.Series,
        candidates: tuple[str | ProphetVariantParameters, ...],
        prophet_model_ids: tuple[str, ...],
        reference_model_ids: tuple[str, ...],
        run_number: int,
        run_root: Path,
    ) -> None:
        run_started = perf_counter()

        initial_history_start = (
            split_start - pd.Timedelta(hours=self.experiment_config.cycle_coldstart_hours)
            if mode == "rolling"
            else None
        )

        split_abbreviation = "val" if split == "validation" else split
        run_id = f"{mode}_{split}_{run_number:03d}"
        run_dir = run_root / f"{mode}_{split_abbreviation}"

        if run_dir.exists():
            raise FileExistsError(f"Forecast-model run directory already exists: {run_dir}")

        run_dir.mkdir(parents=True, exist_ok=False)

        forecasts, evaluation_results = run_forecast_comparison(
            candidates,
            fixed_history,
            evaluation_targets,
            evaluation_imputation_mask,
            run_id=run_id,
            experiment_id=self.experiment_config.experiment_id,
            split=split,
            horizon_hours=self.experiment_config.horizon_hours,
            forecast_origin_step_hours=self.experiment_config.forecast_origin_step_hours,
            frequency=self.experiment_config.frequency,
            local_timezone=self.project_config.timezone,
            clip_negative_forecasts=self.experiment_config.negative_forecast_handling == "clip_zero",
            config_version=self.experiment_config.config_version,
            growth=self.experiment_config.growth,
            daily_seasonality=self.experiment_config.daily_seasonality,
            country_holidays=self.experiment_config.country_holidays,
            log_transform=self.experiment_config.log_transform,
            interval_width=self.experiment_config.interval_width,
            uncertainty_samples=self.experiment_config.uncertainty_samples,
            comparison_model_ids=prophet_model_ids,
            reference_model_ids=reference_model_ids,
            nominal_interval_level=self.experiment_config.interval_width,
            mape_min_eligible_watts=self.experiment_config.mape_min_eligible_watts,
            initial_history_start=initial_history_start,
        )

        if split == "validation":
            primary_naive_reference = select_primary_naive_reference(
                evaluation_results["overall_metrics"],
                self.experiment_config.baseline_model_ids,
            )
        else:
            primary_naive_reference = self.experiment_config.primary_naive_reference

        df_to_csv(forecasts, run_dir, "forecasts")

        for name, result in evaluation_results.items():
            df_to_csv(result, run_dir, name)

        df_to_csv(pd.DataFrame({"model_id": [primary_naive_reference]}), run_dir, "primary_naive_reference")

        output_paths = {
            "forecasts": run_dir / "forecasts.csv",
            "primary_naive_reference": run_dir / "primary_naive_reference.csv",
            **{name: run_dir / f"{name}.csv" for name in evaluation_results},
        }

        runtime_seconds = perf_counter() - run_started

        manifest = build_forecast_run_manifest(
            project_root=self.project_config.project_root,
            run_id=run_id,
            experiment_id=self.experiment_config.experiment_id,
            split=split,
            candidate_id=candidate_id,
            config_values={**asdict(self.experiment_config), "comparison_mode": mode},
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
                "fixed_history_start": fixed_history.index[0] if initial_history_start is None else initial_history_start,
                "fixed_history_end": fixed_history.index[-1],
                "first_forecast_origin": forecasts["forecast_origin"].min(),
                "evaluation_end": split_end,
            },
            forecast_origins=tuple(forecasts["forecast_origin"].drop_duplicates().sort_values()),
            model_parameters={
                "comparison_mode": mode,
                "growth": self.experiment_config.growth,
                "daily_seasonality": self.experiment_config.daily_seasonality,
                "country_holidays": self.experiment_config.country_holidays,
                "local_timezone": self.project_config.timezone,
                "log_transform": self.experiment_config.log_transform,
                "interval_width": self.experiment_config.interval_width,
                "variants": [asdict(variant) for variant in self.experiment_config.prophet_variants],
            },
            seasonalities={
                variant.model_id: {
                    "daily": self.experiment_config.daily_seasonality,
                    "weekly": variant.weekly_seasonality,
                    "yearly": variant.yearly_seasonality,
                    "holidays": self.experiment_config.country_holidays,
                    "local_timezone": self.project_config.timezone,
                    "log_transform": self.experiment_config.log_transform,
                }
                for variant in self.experiment_config.prophet_variants
            },
            history_rules={
                "fixed_history": (
                    f"last {self.experiment_config.cycle_coldstart_hours}h before the window (matches daily_cycle.py)"
                    if mode == "rolling"
                    else "entire available history before split_start (70/15/15 macro split)"
                ),
                "variants": {
                    variant.model_id: {
                        "history_mode": variant.history_mode,
                        "rolling_window_hours": variant.rolling_window_hours,
                        "retraining_interval_hours": variant.retraining_interval_hours,
                    }
                    for variant in self.experiment_config.prophet_variants
                },
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
            seed=self.experiment_config.seed,
            uncertainty_samples=self.experiment_config.uncertainty_samples,
            runtime_seconds=runtime_seconds,
        )

        save_json(manifest, run_dir / "run_manifest.json")

        build_forecast_model_plot(
            run_dir,
            run_dir,
            split=split,
            comparison_mode=mode,
            baseline_model_ids=self.experiment_config.baseline_model_ids,
            variant_model_ids=prophet_model_ids,
            reference_baseline=cast(str, primary_naive_reference),
        )

        logger.info(
            "Forecast-model experiment completed: mode=%s, run=%s, origins=%d, primary naive reference=%s",
            mode,
            run_id,
            forecasts["forecast_origin"].nunique(),
            primary_naive_reference,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ForecastModelRunner().run()


if __name__ == "__main__":
    main()