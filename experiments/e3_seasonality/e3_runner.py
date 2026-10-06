# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e3_seasonality.e3_runner
# danach: python -m experiments.e3_seasonality.e3_report [run_directory]

# langsame Rampen auf den Standard-Szenarien, Regel und LLM komplett, SYS1 nur für MAE
# raw/ behält je Szenario den vollen Harness-Output

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.evaluation import collect_scenario_results
from experiments.common.harness import (
    COMPARISON_SUMMARY_FILE,
    read_anomaly_rows,
    read_llm_prompt,
    run_scenario,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.e3_seasonality.e3_config import (
    RESULTS_FILE,
    RUN_PREFIX,
    E3Config,
)
from experiments.e3_seasonality.e3_evaluation import DRIFT_RESULT_COLUMNS
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e3_config: E3Config) -> Path:
    systems = (e3_config.reference_system, e3_config.rule_system, e3_config.llm_system)
    configs = {system: SYS_VARIANTS[system] for system in systems}
    llm_config = configs[e3_config.llm_system].llm_config
    assert llm_config is not None
    llm_prompt = read_llm_prompt(llm_config.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e3_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "e3_config": asdict(e3_config),
            "llm_config": asdict(llm_config),
            "numerical_analysis_config": asdict(
                configs[e3_config.rule_system].numerical_analysis_config
            ),
        },
    )
    scenario_results: list[pd.DataFrame] = []

    for cutover_id, kinds in e3_config.kinds_by_cutover.items():
        cutover_date = STANDARD_CONFIG.cutover_dates[cutover_id]
        scenarios = build_standard_scenarios(cutover_date, kinds)

        for kind, scenario in scenarios.items():
            scenario_name = f"{kind}_{cutover_date}"
            scenario_directory = raw_directory / scenario_name
            logger.info("E3 drift %s", scenario_name)

            run_scenario(
                scenario,
                configs,
                scenario_directory,
                run_id=f"{run_directory.name}_{scenario_name}",
                llm_prompt=llm_prompt,
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

    logger.info("E3 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E3Config())


if __name__ == "__main__":
    main()
