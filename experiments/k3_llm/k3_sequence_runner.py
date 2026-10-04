# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.k3_llm.k3_sequence_runner
# danach: python -m experiments.k3_llm.k3_report

# Ebene 2: alle Modelle Tag für Tag im Kreislauf auf einem Cutover der Standard-Szenarien, nur für die Modellwahl

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
from experiments.common.standard_config import (
    PROJECT_CONFIG,
    RULE_SYSTEM,
    STANDARD_CONFIG,
)
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k3_llm.k3_config import (
    BASELINE_ID,
    SEQUENCE_RESULTS_FILE,
    SEQUENCE_RUN_PREFIX,
    K3Config,
    build_sequence_configs,
)
from experiments.common.evaluation import collect_scenario_results
from experiments.k3_llm.k3_evaluation import SEQUENCE_RESULT_COLUMNS
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(k3_config: K3Config) -> Path:
    cutover_date = STANDARD_CONFIG.cutover_dates[k3_config.sequence_cutover]
    scenarios = build_standard_scenarios(
        cutover_date,
        k3_config.sequence_kinds,
    )

    configs = build_sequence_configs(
        k3_config.model_variants, k3_config.base_llm_config
    )
    if k3_config.include_rule_based_baseline:
        configs[BASELINE_ID] = SYS_VARIANTS[RULE_SYSTEM]

    llm_prompt = read_llm_prompt(k3_config.base_llm_config.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k3_output_dir,
        SEQUENCE_RUN_PREFIX,
        {"k3_config": asdict(k3_config), "standard_config": asdict(STANDARD_CONFIG)},
    )

    scenario_results: list[pd.DataFrame] = []

    for kind, scenario in scenarios.items():
        scenario_directory = raw_directory / kind
        logger.info(
            "Running K3 model sequence %s (cutover=%s) over %d decision times, %d configs...",
            kind,
            cutover_date,
            len(scenario.decision_times),
            len(configs),
        )
        run_scenario(
            scenario,
            configs,
            scenario_directory,
            run_id=f"{run_directory.name}_{kind}",
            llm_prompt=llm_prompt,
        )
        scenario_results.append(
            collect_scenario_results(
                pd.read_csv(scenario_directory / COMPARISON_SUMMARY_FILE),
                read_anomaly_rows(scenario_directory),
                kind=kind,
                cutover_date=cutover_date,
                columns=SEQUENCE_RESULT_COLUMNS,
            )
        )

    df_to_csv(
        pd.concat(scenario_results, ignore_index=True),
        raw_directory,
        SEQUENCE_RESULTS_FILE,
    )

    logger.info("K3 model-sequence comparison completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K3Config())


if __name__ == "__main__":
    main()
