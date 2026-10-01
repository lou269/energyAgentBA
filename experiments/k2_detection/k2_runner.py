# conda activate forecasting-env
# python -m experiments.k2_detection.k2_runner
# danach: python -m experiments.k2_detection.k2_report

# Schwellen der Anomalieerkennung: je Cutover die Standard-Szenarien, erst isoliert (nur Detektor, ohne Reset) -> Einzeltag-Schwelle und Streak-Empfindlichkeit gewählt
# -> dann im Kreislauf mit Reset (rule, ohne LLM) mit genau diesen Schwellen

import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import run_scenario_in_scratch
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k2_detection.k2_calibration import apply_calibration, calibrate
from experiments.k2_detection.k2_config import (
    CALIBRATION_FILES,
    RESULTS_FILE,
    RUN_PREFIX,
    K2Config,
    build_adaption_configs,
    build_isolated_configs,
)
from experiments.k2_detection.k2_evaluation import (
    read_scenario_results,
    summarize_calibration,
)
from src.config.config_forecasting import CycleConfig, NumericalAnalysisConfig
from src.pipeline.io import (
    create_experiment_run,
    df_to_csv,
    read_raw_json,
    save_json,
)

logger = logging.getLogger(__name__)


def run_mode(
    run_directory: Path,
    *,
    mode: str,
    kinds: tuple[str, ...],
    variants: dict[str, CycleConfig],
) -> pd.DataFrame:
    scenario_results: list[pd.DataFrame] = []

    for cutover_date in STANDARD_CONFIG.cutover_dates:
        scenarios = build_standard_scenarios(
            cutover_date,
            kinds,
            margin_before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
            margin_after_days=STANDARD_CONFIG.margin_after_days,
        )

        for kind in kinds:
            scenario_name = f"{kind}_{cutover_date}"
            logger.info("K2 %s, %s", scenario_name, mode)

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

    return pd.concat(scenario_results, ignore_index=True)


def run(k2_config: K2Config) -> Path:
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k2_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k2_config": asdict(k2_config),
        },
    )

    isolated = run_mode(
        run_directory,
        mode="isolated",
        kinds=k2_config.isolated_kinds,
        variants=build_isolated_configs(),
    )
    analysis_config = NumericalAnalysisConfig()
    calibration = calibrate(
        isolated,
        single_day_scales=analysis_config.single_day_scales,
        target_alarm_pct=k2_config.target_alarm_pct,
        threshold_values={
            "weekday": k2_config.weekday_streak_thresholds,
            "weekly": k2_config.weekly_streak_thresholds,
            "long_term": k2_config.long_term_streak_thresholds_pct,
        },
        streak_tolerance_window_days=analysis_config.streak_tolerance_window_days,
        rolling_window_min_coverage=analysis_config.rolling_window_min_coverage,
        sustained_anomaly_streak_days=analysis_config.sustained_anomaly_streak_days,
        min_sustained_scales=analysis_config.min_sustained_scales,
        control_reset_tolerance_days=k2_config.control_reset_tolerance_days,
    )
    for name, table in calibration.items():
        df_to_csv(table, raw_directory, CALIBRATION_FILES[name])

    loop_config = apply_calibration(
        analysis_config,
        summarize_calibration(
            calibration,
            k2_config.uncounted_cutovers,
            k2_config.max_false_new_pattern,
        ),
        k2_config.gate_threshold_decimals,
    )
    run_config = read_raw_json(run_directory, "run_config")
    run_config["numerical_analysis_config"] = asdict(loop_config)
    save_json(run_config, raw_directory / "run_config.json")

    adaption = run_mode(
        run_directory,
        mode="adaption",
        kinds=k2_config.kinds,
        variants=build_adaption_configs(loop_config),
    )
    df_to_csv(
        pd.concat([isolated, adaption], ignore_index=True), raw_directory, RESULTS_FILE
    )

    logger.info("K2 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K2Config())


if __name__ == "__main__":
    main()
