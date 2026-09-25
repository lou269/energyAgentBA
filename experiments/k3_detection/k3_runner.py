# conda activate forecasting-env
# python -m experiments.k3_detection.k3_runner
# danach: python -m experiments.k3_detection.k3_report

# Referenzfenster und Schwellen der Anomalieerkennung: je Cutover die Standard-Szenarien, isoliert und im Kreislauf mit Reset (rule, ohne LLM).
# Am Ende die Kalibrierung der Schwellen auf den isolated-Läufen

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import run_scenario_in_scratch
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k3_detection.k3_calibration import calibrate
from experiments.k3_detection.k3_config import (
    CALIBRATION_FILES,
    RESULTS_FILE,
    RUN_PREFIX,
    K3Config,
    build_mode_configs,
    kinds_by_mode,
)
from experiments.k3_detection.k3_evaluation import read_scenario_results
from src.config.config_forecasting import NumericalAnalysisConfig
from src.pipeline.io import create_experiment_run, df_to_csv

logger = logging.getLogger(__name__)


def run(k3_config: K3Config) -> Path:
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k3_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k3_config": asdict(k3_config),
            # mit diesen Schwellen läuft der Kreislauf
            "numerical_analysis_config": asdict(NumericalAnalysisConfig()),
        },
    )
    scenario_results: list[pd.DataFrame] = []

    for cutover_date in STANDARD_CONFIG.cutover_dates:
        scenarios = build_standard_scenarios(cutover_date, k3_config.kinds)

        for mode, variants in build_mode_configs(k3_config.reference_windows).items():
            for kind in kinds_by_mode(k3_config)[mode]:
                scenario_name = f"{kind}_{cutover_date}"
                logger.info("K3 %s, %s", scenario_name, mode)

                summary, anomaly = run_scenario_in_scratch(
                    scenarios[kind],
                    variants,
                    run_id=f"{run_directory.name}_{scenario_name}_{mode}",
                )
                scenario_results.append(
                    read_scenario_results(
                        summary,
                        anomaly,
                        mode=mode,
                        kind=kind,
                        cutover_date=cutover_date,
                    )
                )

    results = pd.concat(scenario_results, ignore_index=True)
    df_to_csv(results, raw_directory, RESULTS_FILE)

    calibration = calibrate(results, k3_config, NumericalAnalysisConfig())
    for name, table in calibration.items():
        df_to_csv(table, raw_directory, CALIBRATION_FILES[name])

    logger.info("K3 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K3Config())


if __name__ == "__main__":
    main()
