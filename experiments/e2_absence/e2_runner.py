# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e2_absence.e2_runner [full|precheck]
# vorher einmal in nilmtk-env: python -m experiments.e2_absence.e2_select_channels
# danach: python -m experiments.e2_absence.e2_report [full|precheck]

# Systeme je Kontextvariante aus E2Config.ctx_systems: ohne (CTX0) und mit (CTX1) und per Tool (CTX2) Kalenderkontext
# precheck: nur SYS1/SYS2 ohne LLM, zeigt ob und wann der Urlaub das Gate öffnet

import logging
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from experiments.common.harness import read_llm_prompt, run_scenario
from experiments.common.scenarios import load_target
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.e2_absence.e2_config import (
    COMPARISON_FILE,
    PRECHECK_RUN_PREFIX,
    REDUCTION_FILE,
    RUN_PREFIX,
    E2Config,
)
from experiments.e2_absence.e2_evaluation import summarize_reduction_by_day
from experiments.e2_absence.e2_scenarios import build_absence_scenarios
from experiments.e2_absence.e2_selection import (
    load_calendar_events,
    resolve_absence_window,
)
from src.config.config_forecasting import SYS_VARIANTS, LLMConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(e2_config: E2Config, run_prefix: str) -> Path:
    calendar_events = load_calendar_events(e2_config.calendar_events_file)
    window_start, window_end = resolve_absence_window(
        calendar_events, e2_config.active_absence_event_id
    )
    scenarios = build_absence_scenarios(
        e2_config, calendar_events, window_start, window_end
    )
    llm_prompt = read_llm_prompt(LLMConfig.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e2_output_dir,
        run_prefix,
        {"e2_config": asdict(e2_config)},
    )

    # wie stark die Urlaubswoche Mains überhaupt senkt, unabhängig von den Schwellen
    df_to_csv(
        summarize_reduction_by_day(
            load_target(e2_config.split)[0],
            scenarios["ctx0"].target_series,
            window_start=window_start,
            window_end=window_end,
        ),
        raw_directory,
        REDUCTION_FILE,
    )

    results = []
    for ctx, systems in e2_config.ctx_systems.items():
        scenario = scenarios[ctx]
        logger.info(
            "Running E2/%s over %d decision times...", ctx, len(scenario.decision_times)
        )
        configs = {label: SYS_VARIANTS[system] for label, system in systems.items()}
        results.append(
            run_scenario(
                scenario,
                configs,
                raw_directory / ctx,
                run_id=f"{run_directory.name}_{ctx}",
                llm_prompt=llm_prompt,
            )
        )

    combined = pd.concat(results, ignore_index=True)
    df_to_csv(combined, raw_directory, COMPARISON_FILE)

    logger.info("E2 completed: %d rows written to %s", len(combined), raw_directory)
    return run_directory


def main() -> None:
    part = sys.argv[1] if len(sys.argv) > 1 else "full"
    logging.basicConfig(level=logging.INFO)
    e2_config = E2Config()

    if part == "precheck":
        run(
            replace(e2_config, ctx_systems=e2_config.precheck_ctx_systems),
            PRECHECK_RUN_PREFIX,
        )
    else:
        run(e2_config, RUN_PREFIX)


if __name__ == "__main__":
    main()
