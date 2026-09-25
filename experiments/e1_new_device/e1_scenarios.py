from collections.abc import Sequence

import pandas as pd

from experiments.common.scenarios import (
    build_decision_times,
    crop_history_for_coldstart,
    load_target,
    scenario_without_calendar,
    subtract_channels_in_window,
)
from experiments.common.standard_config import LOCAL_TIMEZONE, PROJECT_CONFIG
from experiments.e1_new_device.e1_config import DEVICES_HOURLY_FILE, E1Config
from src.common.timestamps import local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def load_device_hourly(e1_config: E1Config) -> pd.DataFrame:
    # Ausgabe von e1_device_check (nilmtk-env)
    devices_hourly = pd.read_csv(
        PROJECT_CONFIG.e1_output_dir
        / e1_config.device_selection_subdir
        / f"{DEVICES_HOURLY_FILE}.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )

    return devices_hourly[list(e1_config.device_meter_keys)]


def hide_device_before_cutover(
    mains_series: pd.Series,
    devices_hourly: pd.DataFrame,
    device_meter_keys: Sequence[str],
    cutover_time: pd.Timestamp,
) -> pd.Series:
    # vor dem Cutover wird das Gerät herausgerechnet, ab dem Cutover kommt es also neu dazu
    return subtract_channels_in_window(
        mains_series,
        devices_hourly,
        device_meter_keys,
        window_start=mains_series.index[0],
        window_end=cutover_time,
    )


def build_e1_scenario(
    e1_config: E1Config, apply_device_injection: bool = True
) -> ScenarioData:
    # Entscheidungstage um den Cutover, Historie ab Kaltstart, das Gerät vor dem Cutover herausgerechnet
    mains_series, target_imputed, value_implausible = load_target()
    cutover_time = local_midnight_utc(e1_config.cutover_date, LOCAL_TIMEZONE)

    decision_times = build_decision_times(
        cutover_time,
        cutover_time,
        margin_before_days=e1_config.margin_before_days,
        margin_after_days=e1_config.margin_after_days,
    )
    history = crop_history_for_coldstart(mains_series, decision_times[0])

    # Kontrolllauf: dieselben Tage, das Gerät ist durchgehend drin
    if apply_device_injection:
        history = hide_device_before_cutover(
            history,
            load_device_hourly(e1_config),
            e1_config.device_meter_keys,
            cutover_time,
        )

    return scenario_without_calendar(
        history, decision_times, target_imputed, value_implausible
    )
