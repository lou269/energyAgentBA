# open -a Ollama
# conda run -n forecasting-env python -m experiments.proposal_experiments.e2_absence.e2_runner


# Fünf Läufe: SYS1 (Referenz, adaptionsfrei) + SYS2 (Regel) und SYS3 (LLM) je einmal ohne (CTX0) und mit (CTX1) Kalenderkontext.

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e2_absence.e2_config import (
    ACTIVE_ABSENCE_EVENT_ID,
    CALENDAR_EVENTS_FILE,
    COLDSTART_HOURS,
    DECISION_TIME_MARGIN_AFTER_DAYS,
    DECISION_TIME_MARGIN_BEFORE_DAYS,
)
from experiments.proposal_experiments.e2_absence.e2_scenarios import (
    build_ctx_scenarios,
    subtract_presence_channels,
)
from experiments.proposal_experiments.e2_absence.e2_selection import (
    build_decision_times,
    load_calendar_events,
    resolve_absence_window,
    select_channels_for_subtraction,
)
from src.config.config_forecasting import PreprocessingConfig
from src.config.project_config import ProjectConfig, ensure_project_directories
from src.llm.llm_run_artifacts import load_prompt
from src.llm.llm_runner import PROMPT_DIRECTORY
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.cycle_variants import SYS_VARIANTS
from src.preprocessing.preprocessing_runner import run_preprocessing

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def _read_canonical(project_config: ProjectConfig, name: str) -> pd.DataFrame:
    return pd.read_csv(
        project_config.canonical_output_dir / f"{name}.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )


def _read_target_column(project_config: ProjectConfig) -> str:
    canonical_manifest = pd.read_csv(project_config.canonical_output_dir / "canonical_manifest.csv")

    if len(canonical_manifest) != 1:
        raise ValueError("Canonical manifest must contain exactly one mains target.")

    return str(canonical_manifest.iloc[0]["column_name"])


def _read_absence_channel_selection() -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking_file = OUTPUT_DIR / "absence_channel_ranking.csv"
    data_file = OUTPUT_DIR / "absence_channel_data_hourly.csv"

    if not ranking_file.is_file() or not data_file.is_file():
        raise FileNotFoundError(
            "Run 'conda run -n nilmtk-env python -m "
            "experiments.proposal_experiments.e2_absence.select_absence_channels' first - "
            f"missing {ranking_file} and/or {data_file}."
        )

    ranking = pd.read_csv(ranking_file)
    data_hourly = pd.read_csv(data_file, parse_dates=["timestamp"], index_col="timestamp")

    return ranking, data_hourly


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    project_config = ProjectConfig()
    ensure_project_directories(project_config)

    target_column = _read_target_column(project_config)

    preprocessing_result = run_preprocessing(
        _read_canonical(project_config, "canonical_data_15min"),
        _read_canonical(project_config, "canonical_quality_15min"),
        _read_canonical(project_config, "canonical_data_hourly"),
        _read_canonical(project_config, "canonical_quality_hourly"),
        PreprocessingConfig(),
    )

    mains_series = preprocessing_result.treated_hourly[target_column]

    calendar_events = load_calendar_events(CALENDAR_EVENTS_FILE)
    window_start, window_end = resolve_absence_window(calendar_events, ACTIVE_ABSENCE_EVENT_ID)
    decision_times = build_decision_times(
        window_start,
        window_end,
        margin_before_days=DECISION_TIME_MARGIN_BEFORE_DAYS,
        margin_after_days=DECISION_TIME_MARGIN_AFTER_DAYS,
    )

    ranking, appliance_data_hourly = _read_absence_channel_selection()
    selected_channels = select_channels_for_subtraction(ranking)

    logger.info(
        "Subtracting %d channel(s) for the absence week: %s",
        len(selected_channels), ", ".join(selected_channels),
    )

    absence_adjusted_series = subtract_presence_channels(
        mains_series,
        appliance_data_hourly,
        selected_channels,
        window_start=window_start,
        window_end=window_end,
    )

    ctx0_scenario, ctx1_scenario = build_ctx_scenarios(
        absence_adjusted_series,
        coldstart_hours=COLDSTART_HOURS,
        decision_times=decision_times,
        calendar_events=calendar_events,
    )

    sys3_config = SYS_VARIANTS["SYS3"]
    assert sys3_config.llm_config is not None
    llm_prompt = load_prompt(PROMPT_DIRECTORY / f"prompt_{sys3_config.llm_config.prompt_version}.txt")

    ctx0_dir = OUTPUT_DIR / "ctx0"
    ctx1_dir = OUTPUT_DIR / "ctx1"
    ctx0_dir.mkdir(parents=True, exist_ok=True)
    ctx1_dir.mkdir(parents=True, exist_ok=True)

    ctx0_configs = {
        "SYS1": SYS_VARIANTS["SYS1"],
        "SYS2_CTX0": SYS_VARIANTS["SYS2"],
        "SYS3_CTX0": sys3_config,
    }
    ctx1_configs = {
        "SYS2_CTX1": SYS_VARIANTS["SYS2"],
        "SYS3_CTX1": sys3_config,
    }

    logger.info("Running E2/CTX0 (no calendar context) over %d decision times...", len(decision_times))
    ctx0_result = run_comparison(ctx0_scenario, ctx0_configs, ctx0_dir, llm_prompt=llm_prompt)

    logger.info("Running E2/CTX1 (with calendar context) over %d decision times...", len(decision_times))
    ctx1_result = run_comparison(ctx1_scenario, ctx1_configs, ctx1_dir, llm_prompt=llm_prompt)

    combined = pd.concat([ctx0_result, ctx1_result], ignore_index=True)
    combined.to_csv(OUTPUT_DIR / "e2_comparison_summary.csv", index=False)

    logger.info("E2 completed: %d rows written to %s", len(combined), OUTPUT_DIR / "e2_comparison_summary.csv")


if __name__ == "__main__":
    main()