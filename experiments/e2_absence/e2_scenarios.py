import logging
from collections.abc import Mapping
from dataclasses import replace

import pandas as pd

from experiments.common.scenarios import (
    build_decision_times,
    crop_history_for_coldstart,
    load_target,
    scenario_without_calendar,
    subtract_channels_in_window,
)
from experiments.common.standard_config import PROJECT_CONFIG
from experiments.e2_absence.e2_config import (
    CHANNEL_DATA_FILE,
    CHANNEL_RANKING_FILE,
    E2Config,
)
from src.pipeline.comparison_harness import ScenarioData

logger = logging.getLogger(__name__)


def build_ctx_scenarios(
    target_series: pd.Series,
    decision_times: tuple[pd.Timestamp, ...],
    calendar_events: tuple[Mapping[str, object], ...],
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
) -> dict[str, ScenarioData]:
    ctx0 = scenario_without_calendar(
        target_series, decision_times, target_imputed, value_implausible
    )
    ctx1 = replace(
        ctx0,
        calendar_events=calendar_events,
        calendar_source_available=True,
        calendar_source="user_calendar",
    )

    return {"ctx0": ctx0, "ctx1": ctx1}


def read_channel_selection(e2_config: E2Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Ausgabe von e2_select_channels (nilmtk-env)
    selection_directory = (
        PROJECT_CONFIG.e2_output_dir / e2_config.channel_selection_subdir
    )
    ranking = pd.read_csv(selection_directory / f"{CHANNEL_RANKING_FILE}.csv")
    data_hourly = pd.read_csv(
        selection_directory / f"{CHANNEL_DATA_FILE}.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )

    return ranking, data_hourly


def build_absence_scenarios(
    e2_config: E2Config,
    calendar_events: tuple[Mapping[str, object], ...],
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> dict[str, ScenarioData]:
    # Urlaubswoche: die gewählten Kanäle im Fenster aus Mains herausgerechnet, einmal ohne (CTX0) und einmal mit Kalender (CTX1)
    mains_series, target_imputed, value_implausible = load_target()
    ranking, appliance_data_hourly = read_channel_selection(e2_config)
    # die Auswahl hat e2_select_channels schon getroffen
    selected_channels = ranking.loc[ranking["is_selected"], "meter_key"].tolist()
    logger.info(
        "Subtracting %d channel(s) for the absence week: %s",
        len(selected_channels),
        ", ".join(selected_channels),
    )

    decision_times = build_decision_times(
        window_start,
        window_end,
        margin_before_days=e2_config.decision_time_margin_before_days,
        margin_after_days=e2_config.decision_time_margin_after_days,
    )
    absence_adjusted_series = subtract_channels_in_window(
        crop_history_for_coldstart(mains_series, decision_times[0]),
        appliance_data_hourly,
        selected_channels,
        window_start=window_start,
        window_end=window_end,
    )

    return build_ctx_scenarios(
        absence_adjusted_series,
        decision_times,
        calendar_events,
        target_imputed,
        value_implausible,
    )
