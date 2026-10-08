# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.proactive_cycle.pc_runner
# danach: python -m experiments.proactive_cycle.pc_report [run_directory]

# Prognose ohne Adaption und ohne Aufruf 1, danach je Tag der Ausblick-Aufruf

import logging
from dataclasses import asdict, replace
from pathlib import Path

from experiments.common.harness import read_llm_prompt
from experiments.common.standard_config import (
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.proactive_cycle.pc_config import (
    OUTLOOK_FILE,
    RUN_PREFIX,
    ProactiveCycleConfig,
)
from experiments.proactive_cycle.pc_loop import run_outlook_days
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run

logger = logging.getLogger(__name__)


def run(proactive_cycle_config: ProactiveCycleConfig) -> Path:
    scenario = build_standard_scenarios(
        proactive_cycle_config.cutover_date,
        ("control",),
        margin_before_days=0,
        margin_after_days=proactive_cycle_config.outlook_days - 1,
    )["control"]
    cycle_config = replace(
        SYS_VARIANTS[proactive_cycle_config.cycle_system], llm_mode="off"
    )
    prompt = read_llm_prompt(proactive_cycle_config.llm_config.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.proactive_cycle_output_dir,
        RUN_PREFIX,
        {
            "proactive_cycle_config": asdict(proactive_cycle_config),
            "standard_config": asdict(STANDARD_CONFIG),
        },
    )

    run_outlook_days(
        scenario,
        cycle_config,
        raw_directory / OUTLOOK_FILE,
        prompt=prompt,
        llm_config=proactive_cycle_config.llm_config,
        decimals=proactive_cycle_config.state_decimals,
        local_timezone=LOCAL_TIMEZONE,
    )

    logger.info("Proactive cycle completed: %s", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(ProactiveCycleConfig())


if __name__ == "__main__":
    main()
