# conda activate forecasting-env
# python -m experiments.scenarios.g5_measurement_error.g5_runner

import logging
from pathlib import Path

import pandas as pd

from src.common.column_naming import channel_data_column, plausibility_column, quality_column
from src.config.config_forecasting import ForecastingConfig, NumericalAnalysisConfig, PreprocessingConfig, SYS_VARIANTS
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.pipeline.comparison_harness import ScenarioData, run_comparison
from src.pipeline.io import next_sequential_number
from src.preprocessing.plausibility_check import build_plausibility_flags

from experiments.proposal_experiments.shared import build_decision_times, load_target_series

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

STUCK_HOURS = 8  # > PreprocessingConfig().stuck_value_min_hours (6h), damit Streak sicher greift


def run() -> None:
    project_config = ProjectConfig()
    ensure_project_directories(project_config)

    mains_series, target_imputed, target_value_implausible, meter_key = load_target_series(project_config)

    coldstart_hours = ForecastingConfig().cycle_coldstart_hours
    anchor_time = mains_series.index[max(coldstart_hours, len(mains_series) // 2)]
    fault_day_start = anchor_time.tz_convert(project_config.timezone).normalize().tz_convert("UTC")
    fault_start = fault_day_start + pd.Timedelta(hours=1)
    fault_end = fault_start + pd.Timedelta(hours=STUCK_HOURS - 1)

    logger.info("Freezing %s..%s at a constant value (meter_key=%s)", fault_start, fault_end, meter_key)

    corrupted_series = mains_series.copy()
    corrupted_series.loc[fault_start:fault_end] = corrupted_series.loc[fault_start]

    corrupted_data = pd.DataFrame({channel_data_column(meter_key, "hourly"): corrupted_series})
    corrupted_quality = pd.DataFrame(True, index=corrupted_series.index, columns=[quality_column(meter_key, "coverage_mask")])

    corrupted_plausibility = build_plausibility_flags(
        corrupted_data,
        corrupted_quality,
        stuck_value_min_hours=PreprocessingConfig().stuck_value_min_hours,
        sample_period_hours=NumericalAnalysisConfig().sample_period_hours_hourly,
        resolution="hourly",
    )[plausibility_column(meter_key)]

    # existierende (echte) Flags behalten, nur die manipulierten Stunden kommen von der frischen Berechnung
    combined_plausibility = target_value_implausible.copy()
    combined_plausibility.update(corrupted_plausibility)

    decision_times = build_decision_times(
        fault_day_start, fault_day_start,
        margin_before_days=0, margin_after_days=1,
        local_timezone=project_config.timezone,
    )

    scenario = ScenarioData(
        target_series=corrupted_series,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=combined_plausibility,
    )

    run_number = next_sequential_number(OUTPUT_DIR, prefix="g5")
    run_directory = OUTPUT_DIR / f"g5_{run_number:03d}"
    run_directory.mkdir(parents=True, exist_ok=False)

    result = run_comparison(
        scenario, {"SYS2": SYS_VARIANTS["SYS2"]}, run_directory, project_config.project_root,
        local_timezone=project_config.timezone,
        run_id=run_directory.name,
        max_consecutive_llm_failures=1,
        max_total_llm_failures=1,
        calendar_lookback_hours=24,
        calendar_lookahead_hours=24,
    )

    logger.info("G5 result:\n%s", result.to_string(index=False))

    # erste decision_time deckt nur den Vortag ab (History-Aufholung), die zweite den Fault-Tag selbst
    classification = result["classification"].iloc[-1] if not result.empty else None

    if classification == "measurement_error":
        logger.info("PASS: fault day %s was classified as measurement_error.", fault_day_start.date())
    else:
        logger.error("FAIL: fault day %s was classified as %r, expected measurement_error.", fault_day_start.date(), classification)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()