# conda activate forecasting-env
# python -m experiments.k4_forecast_model.k4_runner [retraining|seasonality]
# danach: python -m experiments.k4_forecast_model.k4_report [retraining|seasonality] [run_directory]

# retraining: Prophet-Varianten und Baselines auf der Validierung, wählt die produktive Variante
# seasonality: ein Jahr Prognose, Prophet mit und ohne Jahressaisonalität neben dem produktiven C3_30

import logging
import sys
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
from experiments.common.standard_config import (
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.k4_forecast_model.k4_config import (
    REFERENCE_FILE,
    RUN_PREFIX,
    SEASONALITY_FORECASTS_FILE,
    SEASONALITY_RUN_PREFIX,
    SPLIT_DIRECTORY_SUFFIX,
    K4Config,
)
from experiments.k4_forecast_model.k4_evaluation import choose_primary_naive_reference
from src.pipeline.io import create_experiment_run, df_to_csv, read_split_bounds

logger = logging.getLogger(__name__)


def run_retraining(k4_config: K4Config) -> Path:
    np.random.seed(k4_config.seed)

    split = STANDARD_CONFIG.split
    target_series, target_imputed, _target_value_implausible = load_target(split)
    split_start, split_end = read_split_bounds(PROJECT_CONFIG, split)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k4_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k4_config": asdict(k4_config),
        },
    )
    prophet_model_ids = tuple(
        variant.model_id for variant in k4_config.prophet_variants
    )

    for mode in k4_config.comparison_modes:
        history, targets, targets_imputed = slice_history_window(
            target_series,
            target_imputed,
            start=split_start,
            end=split_end,
            history_days=k4_config.mode_history_days[mode],
            split_bounds=(split_start, split_end),
        )

        run_id = f"{run_directory.name}_{mode}_{split}"
        mode_directory = raw_directory / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[split]}"
        mode_directory.mkdir(parents=True, exist_ok=False)

        forecasts, evaluation_results = run_forecast_models(
            k4_config.baseline_model_ids + k4_config.prophet_variants,
            history,
            targets,
            targets_imputed,
            k4_config,
            run_id=run_id,
            experiment_id=k4_config.experiment_id,
            split=split,
            comparison_model_ids=prophet_model_ids,
            reference_model_ids=k4_config.reference_model_ids,
        )

        primary_naive_reference = choose_primary_naive_reference(
            evaluation_results["overall_metrics"],
            split=split,
            baseline_model_ids=k4_config.baseline_model_ids,
            configured_reference=k4_config.primary_naive_reference,
        )

        df_to_csv(forecasts, mode_directory, "forecasts")
        for name, result in evaluation_results.items():
            df_to_csv(result, mode_directory, name)
        df_to_csv(
            pd.DataFrame({"model_id": [primary_naive_reference]}),
            mode_directory,
            REFERENCE_FILE,
        )

        logger.info(
            "Forecast-model experiment completed: mode=%s, run=%s, origins=%d, primary naive reference=%s",
            mode,
            run_id,
            forecasts["forecast_origin"].nunique(),
            primary_naive_reference,
        )

    return run_directory


def run_seasonality(k4_config: K4Config) -> Path:
    np.random.seed(k4_config.seed)

    target_series, target_imputed, _target_value_implausible = load_target(
        STANDARD_CONFIG.split
    )
    split_start, split_end = read_split_bounds(PROJECT_CONFIG, STANDARD_CONFIG.split)
    start, end = local_day_window(
        split_start.tz_convert(LOCAL_TIMEZONE).date().isoformat(),
        k4_config.seasonality_days,
    )
    # die ganze Historie vor dem Start, C3_30 schneidet sich davon selbst die letzten 30 Tage ab
    history, targets, targets_imputed = slice_history_window(
        target_series,
        target_imputed,
        start=start,
        end=end,
        history_days=None,
        split_bounds=(split_start, split_end),
    )

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k4_output_dir,
        SEASONALITY_RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k4_config": asdict(k4_config),
        },
    )
    logger.info("K4 seasonality %s, %d days", start, k4_config.seasonality_days)

    forecasts, _evaluation_results = run_forecast_models(
        k4_config.baseline_model_ids + k4_config.seasonality_variants,
        history,
        targets,
        targets_imputed,
        k4_config,
        run_id=run_directory.name,
        experiment_id=k4_config.experiment_id,
        split=STANDARD_CONFIG.split,
        comparison_model_ids=tuple(
            variant.model_id for variant in k4_config.seasonality_variants
        ),
        reference_model_ids=k4_config.baseline_model_ids,
    )
    df_to_csv(forecasts, raw_directory, SEASONALITY_FORECASTS_FILE)

    logger.info("K4 seasonality completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "retraining"
    logging.basicConfig(level=logging.INFO)

    if part == "seasonality":
        run_seasonality(K4Config())
    else:
        run_retraining(K4Config())


if __name__ == "__main__":
    main()
