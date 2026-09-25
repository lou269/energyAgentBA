# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e1_new_device.e1_runner [device|control]
# danach: python -m experiments.e1_new_device.e1_report

# dieselbe Zeitreihe je System aus E1Config.systems: SYS1 (Referenz, adaptionsfrei), SYS2 (Regel), SYS3 (LLM)

import logging
import sys
from dataclasses import asdict
from pathlib import Path

from experiments.common.harness import read_llm_prompt, run_scenario
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.e1_new_device.e1_config import CONTROL_RUN_PREFIX, RUN_PREFIX, E1Config
from experiments.e1_new_device.e1_scenarios import build_e1_scenario
from src.config.config_forecasting import SYS_VARIANTS, LLMConfig
from src.pipeline.io import create_experiment_run

logger = logging.getLogger(__name__)


def run(e1_config: E1Config, apply_device_injection: bool = True) -> Path:
    scenario = build_e1_scenario(e1_config, apply_device_injection)
    configs = {system: SYS_VARIANTS[system] for system in e1_config.systems}

    run_prefix = RUN_PREFIX if apply_device_injection else CONTROL_RUN_PREFIX
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e1_output_dir,
        run_prefix,
        {"e1_config": asdict(e1_config)},
    )

    logger.info(
        "Running E1 (cutover=%s, apply_device_injection=%s) over %d decision times...",
        e1_config.cutover_date,
        apply_device_injection,
        len(scenario.decision_times),
    )
    run_scenario(
        scenario,
        configs,
        raw_directory,
        run_id=run_directory.name,
        llm_prompt=read_llm_prompt(LLMConfig.prompt_version),
    )

    logger.info("E1 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    # control = Kontrolllauf: unveränderte Mains-Reihe statt der Geräte-Injektion, identische decision_times
    part = sys.argv[1] if len(sys.argv) > 1 else "device"
    logging.basicConfig(level=logging.INFO)
    run(E1Config(), apply_device_injection=part != "control")


if __name__ == "__main__":
    main()
