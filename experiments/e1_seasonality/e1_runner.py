# conda activate forecasting-env
# caffeinate -i python -m experiments.e1_seasonality.e1_runner
# danach: python -m experiments.e1_seasonality.e1_report [run_directory]

# Erkennung auf den Standard-Szenarien, nur SYS1 (Regel ordnet ein, keine Adaption, kein LLM)
# raw/ behält je Szenario den vollen Harness-Output

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.evaluation import collect_scenario_results
from experiments.common.harness import (
    COMPARISON_SUMMARY_FILE,
    read_anomaly_rows,
    run_scenario,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.e1_seasonality.e1_config import (
    RESULTS_FILE,
    RUN_PREFIX,
    E1Config,
)
from experiments.e1_seasonality.e1_evaluation import DRIFT_RESULT_COLUMNS
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e1_config: E1Config) -> Path:
    configs = {e1_config.system: SYS_VARIANTS[e1_config.system]}

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e1_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "e1_config": asdict(e1_config),
            "numerical_analysis_config": asdict(
                configs[e1_config.system].numerical_analysis_config
            ),
        },
    )
    scenario_results: list[pd.DataFrame] = []

    for cutover_id, kinds in e1_config.kinds_by_cutover.items():
        cutover_date = STANDARD_CONFIG.cutover_dates[cutover_id]
        scenarios = build_standard_scenarios(cutover_date, kinds)

        for kind, scenario in scenarios.items():
            scenario_name = f"{kind}_{cutover_date}"
            scenario_directory = raw_directory / scenario_name
            logger.info("E1 %s", scenario_name)

            run_scenario(
                scenario,
                configs,
                scenario_directory,
                run_id=f"{run_directory.name}_{scenario_name}",
            )
            scenario_results.append(
                collect_scenario_results(
                    pd.read_csv(scenario_directory / COMPARISON_SUMMARY_FILE),
                    read_anomaly_rows(scenario_directory),
                    kind=kind,
                    cutover_date=cutover_date,
                    columns=DRIFT_RESULT_COLUMNS,
                )
            )

    df_to_csv(
        pd.concat(scenario_results, ignore_index=True),
        raw_directory,
        RESULTS_FILE,
    )

    logger.info("E1 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E1Config())


if __name__ == "__main__":
    main()
