# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.k4_llm.k4_sequence_runner
# danach: python -m experiments.k4_llm.k4_report

# Ebene 2: alle Modelle Tag für Tag im Kreislauf auf einem Cutover der Standard-Szenarien, nur für die Modellwahl

import logging
from dataclasses import asdict
from pathlib import Path

from experiments.common.harness import read_llm_prompt, run_scenario
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k4_llm.k4_config import (
    BASELINE_ID,
    SEQUENCE_RUN_PREFIX,
    K4Config,
    build_sequence_configs,
)
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run

logger = logging.getLogger(__name__)


def run(k4_config: K4Config) -> Path:
    scenarios = build_standard_scenarios(
        k4_config.sequence_cutover_date, k4_config.sequence_kinds
    )

    configs = build_sequence_configs(
        k4_config.model_variants, k4_config.base_llm_config
    )
    if k4_config.include_rule_based_baseline:
        configs[BASELINE_ID] = SYS_VARIANTS["SYS2"]

    llm_prompt = read_llm_prompt(k4_config.base_llm_config.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k4_output_dir,
        SEQUENCE_RUN_PREFIX,
        {"k4_config": asdict(k4_config), "standard_config": asdict(STANDARD_CONFIG)},
    )

    for kind, scenario in scenarios.items():
        logger.info(
            "Running K4 model sequence %s (cutover=%s) over %d decision times, %d configs...",
            kind,
            k4_config.sequence_cutover_date,
            len(scenario.decision_times),
            len(configs),
        )
        run_scenario(
            scenario,
            configs,
            raw_directory / kind,
            run_id=f"{run_directory.name}_{kind}",
            llm_prompt=llm_prompt,
        )

    logger.info("K4 model-sequence comparison completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K4Config())


if __name__ == "__main__":
    main()
