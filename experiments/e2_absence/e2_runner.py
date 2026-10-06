# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.e2_absence.e2_runner [full|precheck]
# vorher einmal in nilmtk-env: python -m experiments.e2_absence.e2_select_channels
# danach: python -m experiments.e2_absence.e2_report [full|precheck]

# je Urlaub aus E2Config.absence_event_ids die Systeme je Kontextvariante aus E2Config.ctx_systems: ohne (CTX0),
# mit (CTX1) und per Tool (CTX2) Kalenderkontext
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
    llm_prompt = read_llm_prompt(LLMConfig.prompt_version)

    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.e2_output_dir,
        run_prefix,
        {"e2_config": asdict(e2_config)},
    )

    results = []
    reductions = []
    for event_id in e2_config.absence_event_ids:
        window_start, window_end = resolve_absence_window(calendar_events, event_id)
        scenarios = build_absence_scenarios(
            e2_config, calendar_events, event_id, window_start, window_end
        )

        # wie stark der Urlaub Mains überhaupt senkt, unabhängig von den Schwellen
        reductions.append(
            summarize_reduction_by_day(
                load_target(e2_config.split)[0],
                scenarios["ctx0"].target_series,
                window_start=window_start,
                window_end=window_end,
            ).assign(event_id=event_id)
        )

        for ctx, systems in e2_config.ctx_systems.items():
            if ctx not in scenarios:
                continue
            scenario = scenarios[ctx]
            logger.info(
                "Running E2/%s/%s over %d decision times...",
                event_id,
                ctx,
                len(scenario.decision_times),
            )
            configs = {label: SYS_VARIANTS[system] for label, system in systems.items()}
            results.append(
                run_scenario(
                    scenario,
                    configs,
                    raw_directory / event_id / ctx,
                    run_id=f"{run_directory.name}_{event_id}_{ctx}",
                    llm_prompt=llm_prompt,
                ).assign(event_id=event_id)
            )

    df_to_csv(pd.concat(reductions, ignore_index=True), raw_directory, REDUCTION_FILE)
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
