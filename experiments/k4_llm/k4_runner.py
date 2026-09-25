# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.k4_llm.k4_runner
# danach: python -m experiments.k4_llm.k4_report

# Ebene 1: synthetische Einzelfälle, je Modell und Wiederholung einmal klassifiziert, dazu die Regel als Baseline

import logging
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from experiments.common.harness import read_llm_prompt
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.k4_llm.k4_cases import (
    classify_cases_with_baseline,
    classify_cases_with_model,
    llm_relevant_cases,
)
from experiments.k4_llm.k4_config import RESULTS_FILE, RUN_PREFIX, K4Config
from src.pipeline.io import create_experiment_run, save_json

logger = logging.getLogger(__name__)


def run(k4_config: K4Config) -> Path:
    run_started = perf_counter()

    cases = llm_relevant_cases()
    prompt = read_llm_prompt(k4_config.base_llm_config.prompt_version)

    run_dir, raw_dir = create_experiment_run(
        PROJECT_CONFIG.k4_output_dir, RUN_PREFIX, {"k4_config": asdict(k4_config)}
    )
    results_file = raw_dir / f"{RESULTS_FILE}.csv"

    logger.info(
        "Starting K4 model comparison: %d models x %d cases x %d repetitions.",
        len(k4_config.model_variants),
        len(cases),
        k4_config.repetitions,
    )

    for variant in k4_config.model_variants:
        classify_cases_with_model(
            variant,
            cases,
            prompt,
            results_file,
            raw_dir,
            llm_config=k4_config.base_llm_config,
            repetitions=k4_config.repetitions,
        )

    if k4_config.include_rule_based_baseline:
        classify_cases_with_baseline(cases, results_file)

    save_json(
        {
            "experiment_id": k4_config.experiment_id,
            "cases": {case.case_id: case.expected_classification for case in cases},
            "runtime_seconds": perf_counter() - run_started,
        },
        raw_dir / "run_manifest.json",
    )

    logger.info("K4 model comparison completed: %s", run_dir)
    return run_dir


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K4Config())


if __name__ == "__main__":
    main()
