# conda activate forecasting-env
# python -m experiments.component_studies.k2_forecast_model.forecast_model_runner

import logging
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from experiments.component_studies.k2_forecast_model.k2_config import SPLIT_DIRECTORY_SUFFIX,ForecastModelExperimentConfig
from experiments.component_studies.k2_forecast_model.k2_scenarios import slice_comparison_window
from src.common.target_series import read_preprocessed_target
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.forecasting.evaluation import select_primary_naive_reference
from src.forecasting.forecasting import run_forecast_comparison
from src.pipeline.io import df_to_csv, next_sequential_number, read_split_bounds
from docs.plots.plot_forecast_model_vergleich import build_forecast_model_plot

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


class ForecastModelRunner:

    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        experiment_config: ForecastModelExperimentConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.experiment_config = experiment_config or ForecastModelExperimentConfig()

    def run(self) -> None:
        np.random.seed(self.experiment_config.seed)
        ensure_project_directories(self.project_config)

        target_series, target_imputed, _target_value_implausible = read_preprocessed_target(self.project_config)
        split_start, split_end = read_split_bounds(self.project_config, self.experiment_config.split)

        run_number = next_sequential_number(OUTPUT_DIR, prefix="k2")
        run_root = OUTPUT_DIR / f"k2_{run_number:03d}"

        for mode in self.experiment_config.comparison_modes:
            history, targets, targets_imputed = slice_comparison_window(
                target_series, target_imputed,
                split_start=split_start,
                split_end=split_end,
                mode=mode,
                coldstart_hours=self.experiment_config.cycle_coldstart_hours,
            )
            self._run_mode(mode, history, targets, targets_imputed, run_root=run_root, run_number=run_number)

    def _run_mode(
        self,
        mode: str,
        history: pd.Series,
        targets: pd.Series,
        targets_imputed: pd.Series,
        *,
        run_root: Path,
        run_number: int,
    ) -> None:
        split = self.experiment_config.split
        prophet_model_ids = tuple(variant.model_id for variant in self.experiment_config.prophet_variants)

        run_id = f"{mode}_{split}_{run_number:03d}"
        run_dir = run_root / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[split]}"
        run_dir.mkdir(parents=True, exist_ok=False)

        forecasts, evaluation_results = run_forecast_comparison(
            (*self.experiment_config.baseline_model_ids, *self.experiment_config.prophet_variants),
            history,
            targets,
            targets_imputed,
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
            reference_model_ids=self.experiment_config.reference_model_ids,
            nominal_interval_level=self.experiment_config.interval_width,
            mape_min_eligible_watts=self.experiment_config.mape_min_eligible_watts,
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
