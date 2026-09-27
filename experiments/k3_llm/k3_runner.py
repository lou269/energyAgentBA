# open -a Ollama
# conda activate forecasting-env
# caffeinate -i python -m experiments.k3_llm.k3_runner
# danach: python -m experiments.k3_llm.k3_report

# Ebene 1: synthetische Einzelfälle, je Modell und Wiederholung einmal klassifiziert, dazu die Regel als Baseline

import logging
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from experiments.common.harness import read_llm_prompt
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.k3_llm.k3_cases import (
    classify_cases_with_baseline,
    classify_cases_with_model,
    llm_relevant_cases,
)
from experiments.k3_llm.k3_config import RESULTS_FILE, RUN_PREFIX, K3Config
from src.pipeline.io import create_experiment_run, save_json

logger = logging.getLogger(__name__)


def run(k3_config: K3Config) -> Path:
    run_started = perf_counter()

    cases = llm_relevant_cases()
    prompt = read_llm_prompt(k3_config.base_llm_config.prompt_version)

    run_dir, raw_dir = create_experiment_run(
        PROJECT_CONFIG.k3_output_dir, RUN_PREFIX, {"k3_config": asdict(k3_config)}
    )
    results_file = raw_dir / f"{RESULTS_FILE}.csv"

    logger.info(
        "Starting K3 model comparison: %d models x %d cases x %d repetitions.",
        len(k3_config.model_variants),
        len(cases),
        k3_config.repetitions,
    )

    for variant in k3_config.model_variants:
        classify_cases_with_model(
            variant,
            cases,
            prompt,
            results_file,
            raw_dir,
            llm_config=k3_config.base_llm_config,
            repetitions=k3_config.repetitions,
        )

    if k3_config.include_rule_based_baseline:
        classify_cases_with_baseline(cases, results_file)

    save_json(
        {
            "experiment_id": k3_config.experiment_id,
            "cases": {case.case_id: case.expected_classification for case in cases},
            "runtime_seconds": perf_counter() - run_started,
        },
        raw_dir / "run_manifest.json",
    )

    logger.info("K3 model comparison completed: %s", run_dir)
    return run_dir


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K3Config())


if __name__ == "__main__":
    main()
