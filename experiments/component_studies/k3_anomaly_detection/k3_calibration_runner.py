# conda activate forecasting-env
# python -m experiments.component_studies.k3_anomaly_detection.k3_calibration_runner [run_directory]

# Stufe 3: Schwellen je Referenzfenster bei gleicher Fehlalarmrate, danach Vergleich der Fenster an diesem Arbeitspunkt

import sys
from pathlib import Path

import pandas as pd

from experiments.component_studies.k3_anomaly_detection.k3_calibration import (
    build_grid_metrics,
    leave_one_cutover_out,
    operating_points_by_cutover,
    select_operating_points,
)
from experiments.component_studies.k3_anomaly_detection.k3_config import K3CalibrationConfig
from src.config.config_forecasting import NumericalAnalysisConfig
from src.pipeline.io import df_to_csv, resolve_run_directory

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    calibration_config = K3CalibrationConfig()
    numerical_analysis_config = NumericalAnalysisConfig()
    run_directory = resolve_run_directory(OUTPUT_DIR, "k3", sys.argv[1] if len(sys.argv) > 1 else None)

    results = pd.read_csv(run_directory / "k3_results.csv", dtype={"cutover_date": str})

    grid_metrics = build_grid_metrics(
        results,
        gate_thresholds=calibration_config.gate_thresholds,
        slow_scale_thresholds=calibration_config.slow_scale_thresholds,
        gate_scales=numerical_analysis_config.gate_scales,
        slow_scales=calibration_config.slow_scales,
        streak_tolerance_window_days=numerical_analysis_config.streak_tolerance_window_days,
        rolling_window_min_coverage=numerical_analysis_config.rolling_window_min_coverage,
        sustained_anomaly_streak_days=numerical_analysis_config.sustained_anomaly_streak_days,
        min_sustained_scales=numerical_analysis_config.min_sustained_scales,
    )

    operating_points = select_operating_points(
        grid_metrics,
        slow_scales=calibration_config.slow_scales,
        target_alarm_rate=calibration_config.target_alarm_rate,
        max_false_new_pattern=calibration_config.max_false_new_pattern,
    )

    tables = {
        "k3_calibration_operating_points": operating_points,
        "k3_calibration_by_cutover": operating_points_by_cutover(
            operating_points, grid_metrics, slow_scales=calibration_config.slow_scales
        ),
        "k3_calibration_loco": leave_one_cutover_out(
            grid_metrics,
            slow_scales=calibration_config.slow_scales,
            target_alarm_rate=calibration_config.target_alarm_rate,
            max_false_new_pattern=calibration_config.max_false_new_pattern,
        ),
    }

    df_to_csv(grid_metrics, run_directory, "k3_calibration_grid")

    for name, table in tables.items():
        df_to_csv(table, run_directory, name)
        print(name)
        print(table.to_string(index=False))
        print()


if __name__ == "__main__":
    main()