# conda activate forecasting-env
# python -m experiments.k2_detection.k2_runner
# danach: python -m experiments.k2_detection.k2_report

# Streak-Schwellen der Niveau-Skalen: gleicher Anteil anhaltender Tage für weekly und long_term
import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from experiments.common.harness import COMPARISON_CONFIG
from experiments.common.scenarios import load_target
from experiments.common.standard_config import (
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.k2_detection.k2_chain import (
    level_shift_values,
    run_chain,
    with_thresholds,
)
from experiments.k2_detection.k2_config import (
    DIAGNOSIS_FILE,
    GRID_FILE,
    RESETS_FILE,
    RUN_PREFIX,
    STREAK_THRESHOLD_COLUMNS,
    K2Config,
)
from experiments.k2_detection.k2_evaluation import (
    diagnosis_case,
    spaced_cutovers,
    summarize_grid,
    sustained_values,
    thresholds_for_share,
)
from src.common.timestamps import analyzed_day_index, local_day
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.daily_analysis import level_shift_thresholds
from src.pipeline.io import (
    create_experiment_run,
    df_to_csv,
    read_raw_json,
    read_split_bounds,
    save_json,
)

logger = logging.getLogger(__name__)


def chain_for(
    series: pd.Series,
    days: pd.DatetimeIndex,
    config: NumericalAnalysisConfig,
    cache: dict,
) -> pd.DataFrame:
    return run_chain(
        series,
        days,
        config,
        cache=cache,
        local_timezone=LOCAL_TIMEZONE,
        calendar_lookback_days=COMPARISON_CONFIG.calendar_lookback_days,
        calendar_lookahead_days=COMPARISON_CONFIG.calendar_lookahead_days,
    )


def run_grid(
    series: pd.Series,
    days: pd.DatetimeIndex,
    sustained: pd.DataFrame,
    analysis_config: NumericalAnalysisConfig,
    k2_config: K2Config,
    cache: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    resets = []

    for share in k2_config.sustained_shares:
        thresholds = thresholds_for_share(sustained, share)
        logger.info("K2 Anteil %s: %s", share, thresholds)
        chain = chain_for(
            series,
            days,
            with_thresholds(
                analysis_config, thresholds["weekly"], thresholds["long_term"]
            ),
            cache,
        )
        rows.append(
            {"share": share}
            | {
                STREAK_THRESHOLD_COLUMNS[scale]: value
                for scale, value in thresholds.items()
            }
        )
        resets.append(chain.loc[chain["reset"], ["analyzed_day"]].assign(share=share))

    return pd.DataFrame(rows), pd.concat(resets, ignore_index=True)


def run_diagnosis(
    configs: dict[str, NumericalAnalysisConfig],
    cutovers: list[str],
    k2_config: K2Config,
) -> pd.DataFrame:
    cases = []

    for cutover_date in cutovers:
        scenarios = build_standard_scenarios(cutover_date, k2_config.diagnosis_kinds)

        for kind in k2_config.diagnosis_kinds:
            logger.info("K2 Diagnose %s_%s", kind, cutover_date)
            scenario = scenarios[kind]
            days = analyzed_day_index(
                pd.DatetimeIndex(scenario.decision_times), LOCAL_TIMEZONE
            ).tz_localize(None)
            # die Scores einer Reihe gelten für beide Einstellungen
            cache: dict = {}
            for label, config in configs.items():
                case = diagnosis_case(
                    chain_for(scenario.target_series, days, config, cache),
                    cutover_date,
                    kind,
                )
                case["config"] = label
                cases.append(case)

    return pd.DataFrame(cases)


def run(k2_config: K2Config) -> Path:
    run_directory, raw_directory = create_experiment_run(
        PROJECT_CONFIG.k2_output_dir,
        RUN_PREFIX,
        {
            "standard_config": asdict(STANDARD_CONFIG),
            "k2_config": asdict(k2_config),
        },
    )

    analysis_config = NumericalAnalysisConfig()
    series = load_target(STANDARD_CONFIG.split)[0]
    split_start, split_end = read_split_bounds(PROJECT_CONFIG, STANDARD_CONFIG.split)
    first_day, last_day = (
        local_day(bound, LOCAL_TIMEZONE).tz_localize(None)
        for bound in (split_start, split_end)
    )
    days = pd.date_range(first_day, last_day, freq="D")

    # die Scores hängen nicht von den Streak-Schwellen ab, ein Cache für die ganze Reihe
    cache: dict = {}
    sustained = sustained_values(
        level_shift_values(
            series, days, analysis_config, cache=cache, local_timezone=LOCAL_TIMEZONE
        ),
        window_days=analysis_config.streak_tolerance_window_days,
        min_days=analysis_config.sustained_anomaly_streak_days,
    )
    grid, resets = run_grid(series, days, sustained, analysis_config, k2_config, cache)
    df_to_csv(grid, raw_directory, GRID_FILE)
    df_to_csv(resets, raw_directory, RESETS_FILE)

    summary = summarize_grid(
        grid, resets, days=len(days), max_resets=k2_config.max_resets
    )
    selected = summary.loc[summary["selected"]].iloc[0]
    chosen_config = with_thresholds(
        analysis_config,
        selected[STREAK_THRESHOLD_COLUMNS["weekly"]],
        selected[STREAK_THRESHOLD_COLUMNS["long_term"]],
    )
    cutovers = spaced_cutovers(
        first_day,
        last_day,
        before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
        after_days=STANDARD_CONFIG.margin_after_days,
    )
    df_to_csv(
        run_diagnosis(
            {"chosen": chosen_config, "current": analysis_config}, cutovers, k2_config
        ),
        raw_directory,
        DIAGNOSIS_FILE,
    )

    run_config = read_raw_json(run_directory, "run_config")
    run_config["numerical_analysis_config"] = asdict(chosen_config)
    run_config["analysis"] = {
        "first_day": str(days[0].date()),
        "last_day": str(days[-1].date()),
        "days": len(days),
        "current_thresholds": level_shift_thresholds(analysis_config),
        "cutovers": cutovers,
    }
    save_json(run_config, raw_directory / "run_config.json")

    logger.info("K2 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K2Config())


if __name__ == "__main__":
    main()
