# conda activate forecasting-env
# python -m experiments.e3_saisonality.e3_runner
# danach: python -m experiments.e3_saisonality.e3_report [run_directory]

# abrupte Stufe und langsame Rampen auf den Standard-Szenarien, System wie im Betrieb mit Regel statt LLM.
# raw/ behält je Szenario den vollen Harness-Output, die States der Gate-Tage werden später dem LLM vorgelegt

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import (
    COMPARISON_SUMMARY_FILE,
    read_anomaly_rows,
    run_scenario,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.e3_saisonality.e3_config import (
    RESULTS_FILE,
    RUN_PREFIX,
    E3Config,
)
from experiments.e3_saisonality.e3_evaluation import read_drift_results
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e3_config: E3Config) -> Path:
    system_config = SYS_VARIANTS[e3_config.system_id]

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e3_output_dir,
        RUN_PREFIX,
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
        scenarios = build_standard_scenarios(
            cutover_date,
            e3_config.kinds,
            margin_before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
            margin_after_days=STANDARD_CONFIG.margin_after_days,
        )

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
        RESULTS_FILE,
    )

    logger.info("E3 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E3Config())


if __name__ == "__main__":
    main()
