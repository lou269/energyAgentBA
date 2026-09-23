# conda activate forecasting-env
# python -m experiments.proposal_experiments.e4_cold_start.e4_runner

# Kaltstart der Prognose, je Starttermin gleiche Auswertungstage und nur unterschiedlich lange Historie davor

import logging
from dataclasses import asdict
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from docs.plots.plot_e4_kaltstart import build_e4_plot
from experiments.proposal_experiments.e_config import E4Config
from experiments.proposal_experiments.e4_cold_start.e4_analysis import (
    assign_days_since_start,
    build_learning_curve,
    find_break_even_days,
    summarize_windows,
)
from experiments.proposal_experiments.e4_cold_start.e4_scenarios import slice_coldstart_window
from src.common.target_series import read_preprocessed_target
from src.config.config_forecasting import ForecastingConfig
from src.config.project_config import ProjectConfig
from src.forecasting.forecasting import run_forecast_comparison
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


class E4Runner:
    def __init__(
        self,
        project_config: ProjectConfig | None = None,
        e4_config: E4Config | None = None,
        forecast_config: ForecastingConfig | None = None,
    ) -> None:
        self.project_config = project_config or ProjectConfig()
        self.e4_config = e4_config or E4Config()
        self.forecast_config = forecast_config or ForecastingConfig()

    def run(self) -> Path:
        np.random.seed(self.forecast_config.seed)

        target_series, target_imputed, _target_value_implausible = read_preprocessed_target(self.project_config)

        variant = self.forecast_config.selected_prophet_variant
        baselines = self.forecast_config.baseline_model_ids
        reference_baseline = cast(str, self.forecast_config.primary_naive_reference)
        candidates = (*baselines, variant)

        run_directory, raw_directory = create_experiment_run(
            self.project_config.e4_output_dir, "e4",
            {
                "e4_config": asdict(self.e4_config),
                "prophet_variant": asdict(variant),
                "reference_baseline": reference_baseline,
                "forecasting_config_version": self.forecast_config.config_version,
                "seed": self.forecast_config.seed,
            },
        )

        forecast_frames: list[pd.DataFrame] = []
        origin_frames: list[pd.DataFrame] = []

        for start_date in self.e4_config.start_dates:
            for coldstart_days in self.e4_config.coldstart_days:
                logger.info("E4 start=%s, Cold Start: %d days", start_date, coldstart_days)

                history, targets, targets_imputed = slice_coldstart_window(
                    target_series, target_imputed,
                    start_date=start_date,
                    coldstart_days=coldstart_days,
                    evaluation_days=self.e4_config.evaluation_days,
                    local_timezone=self.project_config.timezone,
                )

                forecasts, evaluation_results = run_forecast_comparison(
                    candidates, history, targets, targets_imputed,
                    run_id=f"{run_directory.name}_{start_date}_CS{coldstart_days}",
                    experiment_id="E4",
                    split="train",
                    horizon_days=self.forecast_config.horizon_days,
                    forecast_origin_step_days=self.forecast_config.forecast_origin_step_days,
                    frequency=self.forecast_config.frequency,
                    local_timezone=self.project_config.timezone,
                    clip_negative_forecasts=self.forecast_config.negative_forecast_handling == "clip_zero",
                    config_version=self.forecast_config.config_version,
                    growth=self.forecast_config.growth,
                    daily_seasonality=self.forecast_config.daily_seasonality,
                    country_holidays=self.forecast_config.country_holidays,
                    log_transform=self.forecast_config.log_transform,
                    interval_width=self.forecast_config.interval_width,
                    uncertainty_samples=self.forecast_config.uncertainty_samples,
                    comparison_model_ids=(variant.model_id,),
                    reference_model_ids=baselines,
                    nominal_interval_level=self.forecast_config.interval_width,
                    mape_min_eligible_watts=self.forecast_config.mape_min_eligible_watts,
                )

                run_keys = {"start_date": start_date, "coldstart_days": coldstart_days}
                forecast_frames.append(forecasts.assign(**run_keys))
                origin_frames.append(evaluation_results["origin_metrics"].assign(**run_keys))

        daily = assign_days_since_start(pd.concat(origin_frames, ignore_index=True), self.project_config.timezone)
        curve = build_learning_curve(daily, smoothing_days=self.e4_config.smoothing_days)
        break_even = find_break_even_days(
            curve, variant_id=variant.model_id, reference_model_id=reference_baseline,
        )
        windows = summarize_windows(
            daily,
            variant_id=variant.model_id,
            reference_model_id=reference_baseline,
            window_edges_days=self.e4_config.window_edges_days,
        )

        df_to_csv(pd.concat(forecast_frames, ignore_index=True), raw_directory, "forecasts")
        df_to_csv(daily, raw_directory, "origin_metrics")
        df_to_csv(curve, run_directory, "learning_curve")
        df_to_csv(break_even, run_directory, "break_even")
        df_to_csv(windows, run_directory, "window_summary")

        build_e4_plot(
            curve, run_directory, variant_id=variant.model_id, reference_model_id=reference_baseline,
        )

        logger.info("Break-even against %s:\n%s", reference_baseline, break_even.to_string(index=False))
        logger.info("E4 completed, see %s.", run_directory)
        return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    E4Runner().run()


if __name__ == "__main__":
    main()
    
    
