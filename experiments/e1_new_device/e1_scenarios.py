from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pandas as pd

from experiments.common.scenarios import subtract_channels_in_window
from experiments.common.standard_config import LOCAL_TIMEZONE, PROJECT_CONFIG
from experiments.common.standard_scenarios import build_standard_scenarios
from experiments.e1_new_device.e1_config import DEVICES_HOURLY_FILE
from src.common.timestamps import local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def load_devices_hourly(device_selection_subdir: Path) -> pd.DataFrame:
    # Ausgabe von e1_device_check (nilmtk-env)
    return pd.read_csv(
        PROJECT_CONFIG.e1_output_dir
        / device_selection_subdir
        / f"{DEVICES_HOURLY_FILE}.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )


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


def build_e1_scenarios(
    cutover_date: str,
    devices: Mapping[str, tuple[str, ...]],
    devices_hourly: pd.DataFrame,
) -> dict[str, ScenarioData]:
    control = build_standard_scenarios(cutover_date, ("control",))["control"]
    cutover_time = local_midnight_utc(cutover_date, LOCAL_TIMEZONE)

    return {"control": control} | {
        kind: replace(
            control,
            target_series=hide_device_before_cutover(
                control.target_series, devices_hourly, meter_keys, cutover_time
            ),
        )
        for kind, meter_keys in devices.items()
    }
