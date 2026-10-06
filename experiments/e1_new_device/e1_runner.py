# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e1_new_device.e1_runner
# danach: python -m experiments.e1_new_device.e1_report [run_directory]

# echte Geräte ab dem Standard-Cutover, Regel und LLM komplett, SYS1 nur für die Prognosefehler

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
from experiments.common.standard_config import (
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.e1_new_device.e1_config import (
    DEVICE_WINDOWS_FILE,
    RESULTS_FILE,
    RUN_PREFIX,
    E1Config,
)
from experiments.e1_new_device.e1_evaluation import (
    RESULT_COLUMNS,
    summarize_device_window,
)
from experiments.e1_new_device.e1_scenarios import (
    build_e1_scenarios,
    load_devices_hourly,
)
from src.common.timestamps import local_midnight_utc
from src.config.config_forecasting import SYS_VARIANTS
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e1_config: E1Config) -> Path:
    systems = (e1_config.reference_system, e1_config.rule_system, e1_config.llm_system)
    configs = {system: SYS_VARIANTS[system] for system in systems}
    llm_config = configs[e1_config.llm_system].llm_config
    assert llm_config is not None
    llm_prompt = read_llm_prompt(llm_config.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e1_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "e1_config": asdict(e1_config),
            "llm_config": asdict(llm_config),
        },
    )
    devices_hourly = load_devices_hourly(e1_config.device_selection_subdir)
    scenario_results: list[pd.DataFrame] = []
    device_windows: list[dict] = []

    for cutover_id in e1_config.cutover_ids:
        cutover_date = STANDARD_CONFIG.cutover_dates[cutover_id]
        scenarios = build_e1_scenarios(cutover_date, e1_config.devices, devices_hourly)

        for kind, meter_keys in e1_config.devices.items():
            device_windows.append(
                {"cutover_date": cutover_date, "kind": kind}
                | summarize_device_window(
                    devices_hourly,
                    meter_keys,
                    scenarios["control"].target_series,
                    local_midnight_utc(cutover_date, LOCAL_TIMEZONE),
                    STANDARD_CONFIG.margin_after_days,
                )
            )

        for kind, scenario in scenarios.items():
            scenario_name = f"{kind}_{cutover_date}"
            scenario_directory = raw_directory / scenario_name
            logger.info("E1 %s", scenario_name)

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
                    columns=RESULT_COLUMNS,
                )
            )

    df_to_csv(
        pd.concat(scenario_results, ignore_index=True), raw_directory, RESULTS_FILE
    )
    df_to_csv(pd.DataFrame(device_windows), raw_directory, DEVICE_WINDOWS_FILE)

    logger.info("E1 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(E1Config())


if __name__ == "__main__":
    main()
