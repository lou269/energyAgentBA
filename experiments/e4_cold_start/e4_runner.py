# conda activate forecasting-env
# python -m experiments.e4_cold_start.e4_runner
# danach: python -m experiments.e4_cold_start.e4_report

# Kaltstart der Prognose, je Starttermin gleiche Auswertungstage und nur unterschiedlich lange Historie davor

import logging
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common.harness import run_forecast_models
from experiments.common.scenarios import (
    load_target,
    local_day_window,
    slice_history_window,
)
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.e4_cold_start.e4_config import (
    FORECASTS_FILE,
    ORIGIN_METRICS_FILE,
    RUN_PREFIX,
    E4Config,
)
from src.config.config_forecasting import ForecastingConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e4_config: E4Config) -> Path:
    forecast_config = ForecastingConfig()
    np.random.seed(forecast_config.seed)

    target_series, target_imputed, _target_value_implausible = load_target()

    variant = forecast_config.selected_prophet_variant
    baselines = forecast_config.baseline_model_ids

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e4_output_dir,
        RUN_PREFIX,
        {
            "e4_config": asdict(e4_config),
            "prophet_variant": asdict(variant),
            "reference_baseline": forecast_config.primary_naive_reference,
            "forecasting_config_version": forecast_config.config_version,
            "seed": forecast_config.seed,
        },
    )

    forecast_frames: list[pd.DataFrame] = []
    origin_frames: list[pd.DataFrame] = []

    for start_date in e4_config.start_dates:
        start, end = local_day_window(start_date, e4_config.evaluation_days)

        for coldstart_days in e4_config.coldstart_days:
            logger.info("E4 start=%s, Cold Start: %d days", start_date, coldstart_days)

            history, targets, targets_imputed = slice_history_window(
                target_series,
                target_imputed,
                start=start,
                end=end,
                history_days=coldstart_days,
            )

            forecasts, evaluation_results = run_forecast_models(
                baselines + (variant,),
                history,
                targets,
                targets_imputed,
                forecast_config,
                run_id=f"{run_directory.name}_{start_date}_CS{coldstart_days}",
                experiment_id=e4_config.experiment_id,
                split=e4_config.split,
                comparison_model_ids=(variant.model_id,),
                reference_model_ids=baselines,
            )

            forecast_frames.append(
                forecasts.assign(start_date=start_date, coldstart_days=coldstart_days)
            )
            origin_frames.append(
                evaluation_results["origin_metrics"].assign(
                    start_date=start_date, coldstart_days=coldstart_days
                )
            )

    df_to_csv(
        pd.concat(forecast_frames, ignore_index=True), raw_directory, FORECASTS_FILE
    )
    df_to_csv(
        pd.concat(origin_frames, ignore_index=True), raw_directory, ORIGIN_METRICS_FILE
    )

    logger.info("E4 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E4Config())


if __name__ == "__main__":
    main()
