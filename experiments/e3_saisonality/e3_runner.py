# conda activate forecasting-env
# python -m experiments.e3_saisonality.e3_runner [forecast|drift]
# danach: python -m experiments.e3_saisonality.e3_report [forecast|drift] [run_directory]

# forecast: ein Jahr Prognose, Prophet mit und ohne Jahressaisonalität neben dem produktiven C3_30
# drift: abrupte Stufe und langsame Rampen auf den Standard-Szenarien, System wie im Betrieb mit Regel statt LLM.
# raw/ behält je Szenario den vollen Harness-Output, die States der Gate-Tage werden später dem LLM vorgelegt

import logging
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common.harness import (
    COMPARISON_SUMMARY_FILE,
    read_anomaly_rows,
    run_forecast_models,
    run_scenario,
)
from experiments.common.scenarios import (
    load_target,
    local_day_window,
    slice_history_window,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.e3_saisonality.e3_config import (
    DRIFT_RESULTS_FILE,
    DRIFT_RUN_PREFIX,
    FORECAST_RUN_PREFIX,
    ORIGIN_METRICS_FILE,
    E3Config,
)
from experiments.e3_saisonality.e3_evaluation import read_drift_results
from src.config.config_forecasting import SYS_VARIANTS, ForecastingConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run_forecast(e3_config: E3Config) -> Path:
    forecast_config = ForecastingConfig()
    np.random.seed(forecast_config.seed)

    target_series, target_imputed, _target_value_implausible = load_target()
    start, end = local_day_window(
        e3_config.forecast_start_date, e3_config.forecast_days
    )
    # die ganze Historie vor dem Start, C3_30 schneidet sich davon selbst die letzten 30 Tage ab
    history, targets, targets_imputed = slice_history_window(
        target_series, target_imputed, start=start, end=end, history_days=None
    )

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e3_output_dir,
        FORECAST_RUN_PREFIX,
        {
            "e3_config": asdict(e3_config),
            "reference_baseline": forecast_config.primary_naive_reference,
            "forecasting_config_version": forecast_config.config_version,
            "seed": forecast_config.seed,
        },
    )
    logger.info("E3 forecast %s, %d days", start, e3_config.forecast_days)

    _forecasts, evaluation_results = run_forecast_models(
        forecast_config.baseline_model_ids + e3_config.prophet_variants,
        history,
        targets,
        targets_imputed,
        forecast_config,
        run_id=run_directory.name,
        experiment_id=e3_config.experiment_id,
        split=e3_config.split,
        comparison_model_ids=tuple(
            variant.model_id for variant in e3_config.prophet_variants
        ),
        reference_model_ids=forecast_config.baseline_model_ids,
    )
    df_to_csv(evaluation_results["origin_metrics"], raw_directory, ORIGIN_METRICS_FILE)

    logger.info("E3 forecast completed, see %s.", run_directory)
    return run_directory


def run_drift(e3_config: E3Config) -> Path:
    system_config = SYS_VARIANTS[e3_config.system_id]

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e3_output_dir,
        DRIFT_RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "e3_config": asdict(e3_config),
            "numerical_analysis_config": asdict(
                system_config.numerical_analysis_config
            ),
        },
    )
    scenario_results: list[pd.DataFrame] = []

    for cutover_date in STANDARD_CONFIG.cutover_dates:
        scenarios = build_standard_scenarios(cutover_date, e3_config.kinds)

        for kind, scenario in scenarios.items():
            scenario_name = f"{kind}_{cutover_date}"
            scenario_directory = raw_directory / scenario_name
            logger.info("E3 drift %s", scenario_name)

            run_scenario(
                scenario,
                {e3_config.system_id: system_config},
                scenario_directory,
                run_id=f"{run_directory.name}_{scenario_name}",
            )
            scenario_results.append(
                read_drift_results(
                    pd.read_csv(scenario_directory / COMPARISON_SUMMARY_FILE),
                    read_anomaly_rows(scenario_directory),
                    kind=kind,
                    cutover_date=cutover_date,
                )
            )

    df_to_csv(
        pd.concat(scenario_results, ignore_index=True),
        raw_directory,
        DRIFT_RESULTS_FILE,
    )

    logger.info("E3 drift completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "forecast"
    logging.basicConfig(level=logging.INFO)

    if part == "forecast":
        run_forecast(E3Config())
    else:
        run_drift(E3Config())


if __name__ == "__main__":
    main()
