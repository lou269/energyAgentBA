# python -m src.pipeline.pipeline_runner
# python -m src.pipeline.pipeline_runner --configs SYS0,SYS2
# python -m src.pipeline.pipeline_runner --skip-data-preparation
# python -m src.pipeline.pipeline_runner --configs SYS0,SYS1,SYS2,SYS3 --skip-data-preparation
# python -m src.pipeline.pipeline_runner --configs SYS3 --skip-data-preparation

# open -a Ollama

import argparse
import logging
import subprocess

from src.common.column_naming import imputation_column, treated_column
from src.config.config_forecasting import ForecastingConfig, PreprocessingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import build_scenario_from_split_manifest, create_cycle_run_id, run_comparison
from src.pipeline.cycle_variants import SYS_VARIANTS
from src.pipeline.daily_cycle import CycleConfig
from src.pipeline.io import read_canonical_frame, read_target_meter_key
from src.preprocessing.preprocessing_runner import run_preprocessing

logger = logging.getLogger(__name__)

# ingestion/analysis gelten als einmalig erledigt (Rohdaten ändern sich nicht) 
# -> data_preparation hängt von der Kandidatenwahl ab und läuft hier noch als Subprozess, weil es nilmtk braucht 
# und damit nicht in diesem (forecasting-env-)Prozess laufen kann
DATA_PREPARATION_MODULE = "src.data_preparation.data_preparation_runner"
DATA_PREPARATION_ENVIRONMENT = "nilmtk-env"


def run_data_preparation() -> None:
    subprocess.run(
        [
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            DATA_PREPARATION_ENVIRONMENT,
            "python",
            "-m",
            DATA_PREPARATION_MODULE,
        ],
        check=True,
    )


def _parse_configs(labels: str) -> dict[str, CycleConfig]:
    selected: dict[str, CycleConfig] = {}

    for label in labels.split(","):
        label = label.strip()

        if label not in SYS_VARIANTS:
            raise ValueError(f"Unknown config '{label}'. Available: {', '.join(SYS_VARIANTS)}")

        selected[label] = SYS_VARIANTS[label]

    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", default="SYS0,SYS1", help="Comma-separated SYS_VARIANTS labels, e.g. SYS0,SYS2")
    parser.add_argument("--skip-data-preparation", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    project_config = ProjectConfig()
    ensure_project_directories(project_config)

    if not args.skip_data_preparation:
        logger.info("=== data_preparation [%s] ===", DATA_PREPARATION_ENVIRONMENT)
        run_data_preparation()

    target_meter_key = read_target_meter_key(project_config)
    target_column = treated_column(target_meter_key)

    logger.info("Running preprocessing for target column %s...", target_column)

    preprocessing_result = run_preprocessing(
        read_canonical_frame(project_config, "canonical_data_15min"),
        read_canonical_frame(project_config, "canonical_quality_15min"),
        read_canonical_frame(project_config, "canonical_data_hourly"),
        read_canonical_frame(project_config, "canonical_quality_hourly"),
        PreprocessingConfig(),
    )

    configs = _parse_configs(args.configs)

    llm_prompt = None
    real_config = next((config for config in configs.values() if config.llm_mode == "real"), None)

    if real_config is not None:
        assert real_config.llm_config is not None
        llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{real_config.llm_config.prompt_version}.txt")

    scenario = build_scenario_from_split_manifest(
        preprocessing_result.treated_hourly,
        preprocessing_result.split_manifest,
        target_column,
        coldstart_hours=ForecastingConfig().cycle_coldstart_hours,
        target_imputed=preprocessing_result.imputation_mask_hourly[imputation_column(target_meter_key)],
    )

    logger.info("Running daily cycle for configs %s over %d decision times...", ", ".join(configs), len(scenario.decision_times))

    run_id = create_cycle_run_id(project_config.cycle_output_dir, configs)
    run_directory = project_config.cycle_output_dir / run_id

    comparison = run_comparison(scenario, configs, run_directory, project_config.project_root, run_id=run_id, llm_prompt=llm_prompt)

    logger.info("Pipeline completed successfully: %d cycle rows across %d configs.", len(comparison), len(configs))


if __name__ == "__main__":
    main()