# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e5_system_compare.e5_runner
# danach: python -m experiments.e5_system_compare.e5_report [run_directory]

# je Cutover Kontroll- und Ereignisreihe mit SYS1 (ohne Adaption), SYS2 (Regel) und SYS3 (LLM), ohne Kalender

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import (
    COMPARISON_SUMMARY_FILE,
    read_anomaly_rows,
    read_llm_prompt,
    run_scenario,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.e5_system_compare.e5_config import (
    RESULTS_FILE,
    RUN_PREFIX,
    SCENARIO_DIRECTORY,
    E5Config,
)
from experiments.e5_system_compare.e5_evaluation import read_e5_results
from experiments.e5_system_compare.e5_scenarios import build_e5_scenarios
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e5_config: E5Config) -> Path:
    systems = (e5_config.reference_system, e5_config.rule_system, e5_config.llm_system)
    configs = {system: SYS_VARIANTS[system] for system in systems}
    llm_config = configs[e5_config.llm_system].llm_config
    llm_prompt = read_llm_prompt(llm_config.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e5_output_dir,
        RUN_PREFIX,
        {
            "e5_config": asdict(e5_config),
            "standard_config": asdict(STANDARD_CONFIG),
            "llm_config": asdict(llm_config),
            "numerical_analysis_config": asdict(
                configs[e5_config.rule_system].numerical_analysis_config
            ),
        },
    )
    results: list[pd.DataFrame] = []

    for cutover_date in e5_config.cutover_dates:
        scenarios = build_e5_scenarios(
            cutover_date,
            e5_config.events,
            margin_before_days=e5_config.margin_before_days,
            margin_after_days=e5_config.margin_after_days,
        )

        for series, scenario in scenarios.items():
            scenario_name = SCENARIO_DIRECTORY.format(
                series=series, cutover_date=cutover_date
            )
            scenario_directory = raw_directory / scenario_name
            logger.info(
                "E5 %s over %d decision times",
                scenario_name,
                len(scenario.decision_times),
            )

            run_scenario(
                scenario,
                configs,
                scenario_directory,
                run_id=f"{run_directory.name}_{scenario_name}",
                llm_prompt=llm_prompt,
            )
            results.append(
                read_e5_results(
                    pd.read_csv(scenario_directory / COMPARISON_SUMMARY_FILE),
                    read_anomaly_rows(scenario_directory),
                    series=series,
                    cutover_date=cutover_date,
                )
            )

    df_to_csv(pd.concat(results, ignore_index=True), raw_directory, RESULTS_FILE)

    logger.info("E5 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E5Config())


if __name__ == "__main__":
    main()
