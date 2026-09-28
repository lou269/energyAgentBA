# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e4_cold_start.e4_runner
# danach: python -m experiments.e4_cold_start.e4_report

# Kaltstart, je Starttermin gleiche Auswertungstage und nur unterschiedlich lange Historie davor
# E4a: nur die Prognose im Walk-Forward, adaptiv gegen statisch. E4b: der ganze Kreislauf mit SYS3, sauber und mit je einer Injektion

import logging
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.common.harness import (
    read_llm_prompt,
    run_forecast_models,
    run_scenario_in_scratch,
)
from experiments.common.scenarios import (
    load_target,
    local_day_window,
    slice_history_window,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e4_cold_start.e4_config import (
    FORECAST_METRICS_FILE,
    RUN_PREFIX,
    SYSTEM_RESULTS_FILE,
    E4Config,
)
from experiments.e4_cold_start.e4_evaluation import read_system_days
from experiments.e4_cold_start.e4_scenarios import build_system_scenarios
from src.config.config_forecasting import SYS_VARIANTS, ForecastingConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run_forecasts(
    e4_config: E4Config, forecast_config: ForecastingConfig, run_name: str
) -> pd.DataFrame:
    np.random.seed(forecast_config.seed)
    target_series, target_imputed, _target_value_implausible = load_target()

    adaptive = forecast_config.selected_prophet_variant
    static = e4_config.static_variant
    # None heißt nur in K1 "noch wählen", E4 übernimmt die dort gewählte Baseline
    reference = forecast_config.primary_naive_reference
    assert reference is not None
    origin_frames: list[pd.DataFrame] = []

    for start_date in e4_config.start_dates:
        start, end = local_day_window(start_date, e4_config.evaluation_days)

        for coldstart_days in e4_config.forecast_coldstart_days:
            logger.info("E4a start=%s, Cold Start: %d days", start_date, coldstart_days)

            history, targets, targets_imputed = slice_history_window(
                target_series,
                target_imputed,
                start=start,
                end=end,
                history_days=coldstart_days,
            )
            _forecasts, evaluation_results = run_forecast_models(
                (reference, adaptive, static),
                history,
                targets,
                targets_imputed,
                forecast_config,
                run_id=f"{run_name}_{start_date}_CS{coldstart_days}",
                experiment_id=e4_config.experiment_id,
                split=e4_config.split,
                comparison_model_ids=(adaptive.model_id, static.model_id),
                reference_model_ids=(reference,),
            )
            origin_frames.append(
                evaluation_results["origin_metrics"].assign(
                    start_date=start_date, coldstart_days=coldstart_days
                )
            )

    return pd.concat(origin_frames, ignore_index=True)


def run_system(e4_config: E4Config, run_name: str) -> pd.DataFrame:
    system_config = SYS_VARIANTS[e4_config.system]
    assert system_config.llm_config is not None
    llm_prompt = read_llm_prompt(system_config.llm_config.prompt_version)
    scenario_results: list[pd.DataFrame] = []

    for start_date in e4_config.start_dates:
        for coldstart_days in e4_config.system_coldstart_days:
            scenarios = build_system_scenarios(
                start_date,
                coldstart_days,
                e4_config.evaluation_days,
                injection_kinds=e4_config.injection_kinds,
                injection_days=e4_config.injection_days,
            )

            for (scenario, injection_day), scenario_data in scenarios.items():
                logger.info(
                    "E4b start=%s, Cold Start: %d days, %s %s",
                    start_date,
                    coldstart_days,
                    scenario,
                    injection_day,
                )

                summary, anomaly = run_scenario_in_scratch(
                    scenario_data,
                    {e4_config.system: system_config},
                    run_id=f"{run_name}_{start_date}_CS{coldstart_days}_{scenario}_{injection_day}",
                    llm_prompt=llm_prompt,
                )
                scenario_results.append(
                    read_system_days(
                        summary,
                        anomaly,
                        start_date=start_date,
                        coldstart_days=coldstart_days,
                        scenario=scenario,
                        injection_day=injection_day,
                    )
                )

    return pd.concat(scenario_results, ignore_index=True)


def run(e4_config: E4Config) -> Path:
    forecast_config = ForecastingConfig()

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e4_output_dir,
        RUN_PREFIX,
        {
            "e4_config": asdict(e4_config),
            "prophet_variant": asdict(forecast_config.selected_prophet_variant),
            "reference_baseline": forecast_config.primary_naive_reference,
            "forecasting_config_version": forecast_config.config_version,
            "seed": forecast_config.seed,
            # mit diesem System läuft E4b, darin Modell und Prompt-Version
            "system_config": asdict(SYS_VARIANTS[e4_config.system]),
            "standard_config": asdict(STANDARD_CONFIG),
        },
    )

    df_to_csv(
        run_forecasts(e4_config, forecast_config, run_directory.name),
        raw_directory,
        FORECAST_METRICS_FILE,
    )
    df_to_csv(
        run_system(e4_config, run_directory.name), raw_directory, SYSTEM_RESULTS_FILE
    )

    logger.info("E4 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E4Config())


if __name__ == "__main__":
    main()
