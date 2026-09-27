# conda activate forecasting-env
# python -m experiments.k1_forecast_model.k1_runner
# danach: python -m experiments.k1_forecast_model.k1_report

import logging
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common.harness import run_forecast_models
from experiments.common.scenarios import load_target, slice_history_window
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.k1_forecast_model.k1_config import (
    REFERENCE_FILE,
    RUN_PREFIX,
    SPLIT_DIRECTORY_SUFFIX,
    K1Config,
)
from experiments.k1_forecast_model.k1_evaluation import choose_primary_naive_reference
from src.pipeline.io import create_experiment_run, df_to_csv, read_split_bounds

logger = logging.getLogger(__name__)


def run(k1_config: K1Config) -> Path:
    np.random.seed(k1_config.seed)

    target_series, target_imputed, _target_value_implausible = load_target()
    split = k1_config.split
    split_start, split_end = read_split_bounds(PROJECT_CONFIG, split)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k1_output_dir,
        RUN_PREFIX,
        {"k1_config": asdict(k1_config)},
    )
    prophet_model_ids = tuple(
        variant.model_id for variant in k1_config.prophet_variants
    )

    for mode in k1_config.comparison_modes:
        history, targets, targets_imputed = slice_history_window(
            target_series,
            target_imputed,
            start=split_start,
            end=split_end,
            history_days=k1_config.mode_history_days[mode],
        )

        run_id = f"{run_directory.name}_{mode}_{split}"
        mode_directory = raw_directory / f"{mode}_{SPLIT_DIRECTORY_SUFFIX[split]}"
        mode_directory.mkdir(parents=True, exist_ok=False)

        forecasts, evaluation_results = run_forecast_models(
            k1_config.baseline_model_ids + k1_config.prophet_variants,
            history,
            targets,
            targets_imputed,
            k1_config,
            run_id=run_id,
            experiment_id=k1_config.experiment_id,
            split=split,
            comparison_model_ids=prophet_model_ids,
            reference_model_ids=k1_config.reference_model_ids,
        )

        primary_naive_reference = choose_primary_naive_reference(
            evaluation_results["overall_metrics"],
            split=split,
            baseline_model_ids=k1_config.baseline_model_ids,
            configured_reference=k1_config.primary_naive_reference,
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


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K1Config())


if __name__ == "__main__":
    main()
