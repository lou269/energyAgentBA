# conda activate forecasting-env
# python -m experiments.k2_detection.k2_runner
# danach: python -m experiments.k2_detection.k2_report

# Streak-Schwellen der Anomalieerkennung auf den echten Trends der Train-Reihe
import logging
from dataclasses import asdict
from itertools import product
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
from experiments.k2_detection.k2_chain import run_chain, with_thresholds
from experiments.k2_detection.k2_config import (
    DIAGNOSIS_FILE,
    EVENT_HITS_FILE,
    EVENTS_FILE,
    GRID_FILE,
    RUN_PREFIX,
    STREAK_THRESHOLD_COLUMNS,
    K2Config,
)
from experiments.k2_detection.k2_evaluation import (
    analysis_days,
    diagnosis_case,
    event_hits,
    events_in_range,
    find_real_events,
    scenario_days,
    summarize_events,
    summarize_grid,
    summarize_point,
)
from src.common.timestamps import local_day
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
    events: pd.DataFrame,
    analysis_config: NumericalAnalysisConfig,
    k2_config: K2Config,
) -> tuple[pd.DataFrame, dict[tuple[float, ...], pd.DataFrame]]:
    threshold_columns = list(STREAK_THRESHOLD_COLUMNS.values())
    cache: dict = {}
    chains = {}
    rows = []

    for weekday, weekly, long_term in product(
        k2_config.weekday_streak_thresholds,
        k2_config.weekly_streak_thresholds,
        k2_config.long_term_streak_thresholds_pct,
    ):
        logger.info("K2 Raster %s / %s / %s", weekday, weekly, long_term)
        chain = chain_for(
            series,
            days,
            with_thresholds(analysis_config, weekday, weekly, long_term),
            cache,
        )
        chains[(weekday, weekly, long_term)] = chain
        row = dict(zip(threshold_columns, (weekday, weekly, long_term)))
        row.update(
            summarize_point(
                chain,
                events,
                hit_days_before=k2_config.hit_days_before,
                hit_days_after=k2_config.hit_days_after,
            )
        )
        rows.append(row)

    return pd.DataFrame(rows), chains


def run_diagnosis(
    events: pd.DataFrame,
    configs: dict[str, NumericalAnalysisConfig],
    k2_config: K2Config,
) -> pd.DataFrame:
    cases = []

    for cutover_id in k2_config.cutovers:
        cutover_date = STANDARD_CONFIG.cutover_dates[cutover_id]
        scenarios = build_standard_scenarios(
            cutover_date,
            k2_config.diagnosis_kinds,
        )

        for kind in k2_config.diagnosis_kinds:
            logger.info("K2 Diagnose %s_%s", kind, cutover_date)
            scenario = scenarios[kind]
            days = scenario_days(scenario.decision_times, LOCAL_TIMEZONE)
            # die Scores einer Reihe gelten für beide Einstellungen
            cache: dict = {}
            for label, config in configs.items():
                chain = chain_for(scenario.target_series, days, config, cache)
                case = diagnosis_case(
                    chain,
                    cutover_date,
                    kind,
                    events=events,
                    positive_kinds=k2_config.positive_kinds,
                    negative_kinds=k2_config.negative_kinds,
                    hit_days_before=k2_config.hit_days_before,
                    hit_days_after=k2_config.hit_days_after,
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
    days = analysis_days(
        series,
        local_timezone=LOCAL_TIMEZONE,
        first_day=first_day,
        last_day=last_day,
    )
    all_events = find_real_events(
        series,
        local_timezone=LOCAL_TIMEZONE,
        reference_days=k2_config.event_reference_days,
        transition_days=k2_config.event_transition_days,
        min_change_pct=k2_config.event_min_change_pct,
        min_duration_days=k2_config.event_min_duration_days,
        smoothing_days=k2_config.event_smoothing_days,
        share=k2_config.event_share,
        merge_days=k2_config.event_merge_days,
    )
    df_to_csv(all_events, raw_directory, EVENTS_FILE)
    events = events_in_range(
        all_events,
        first_day,
        last_day,
        hit_days_before=k2_config.hit_days_before,
        hit_days_after=k2_config.hit_days_after,
    )

    points, chains = run_grid(series, days, events, analysis_config, k2_config)
    current = level_shift_thresholds(analysis_config)
    summary = summarize_grid(points, k2_config.max_false_resets_per_year, current)
    df_to_csv(summary.ranked, raw_directory, GRID_FILE)

    chosen_config = with_thresholds(
        analysis_config,
        summary.selected["weekday"],
        summary.selected["weekly"],
        summary.selected["long_term"],
    )
    configs = {"chosen": chosen_config, "current": analysis_config}
    # die aktuelle Config liegt im Raster, beide Punkte sind schon gerechnet
    grid_points = {
        "chosen": tuple(summary.selected.values()),
        "current": tuple(current.values()),
    }
    hits = {
        label: event_hits(
            chains[point],
            events,
            hit_days_before=k2_config.hit_days_before,
            hit_days_after=k2_config.hit_days_after,
        )
        for label, point in grid_points.items()
    }
    df_to_csv(
        summarize_events(events, hits["chosen"], hits["current"]),
        raw_directory,
        EVENT_HITS_FILE,
    )
    df_to_csv(
        run_diagnosis(all_events, configs, k2_config), raw_directory, DIAGNOSIS_FILE
    )

    run_config = read_raw_json(run_directory, "run_config")
    run_config["numerical_analysis_config"] = asdict(chosen_config)
    run_config["analysis"] = {
        "first_day": str(days[0].date()),
        "last_day": str(days[-1].date()),
        "days": len(days),
        "events": len(events),
        "current_thresholds": current,
        "hit_days_after": k2_config.hit_days_after,
        "diagnosis_kinds": list(k2_config.diagnosis_kinds),
    }
    save_json(run_config, raw_directory / "run_config.json")

    logger.info("K2 completed, see %s.", run_directory)
    return run_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run(K2Config())


if __name__ == "__main__":
    main()
