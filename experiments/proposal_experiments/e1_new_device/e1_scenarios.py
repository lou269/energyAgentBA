from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.shared import subtract_channels_in_window
from src.pipeline.comparison_harness import ScenarioData


def load_device_hourly(
    device_selection_dir: Path, device_meter_keys: Sequence[str]
) -> pd.DataFrame:
    devices_hourly = pd.read_csv(
        device_selection_dir / "e1_devices_hourly.csv",
        parse_dates=["timestamp"],
        index_col="timestamp",
    )

    return devices_hourly[list(device_meter_keys)]


def build_device_scenario(
    mains_series: pd.Series,
    devices_hourly: pd.DataFrame,
    device_meter_keys: Sequence[str],
    *,
    cutover_time: pd.Timestamp,
    coldstart_days: int,
    decision_times: tuple[pd.Timestamp, ...],
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
    apply_device_injection: bool = True,
) -> ScenarioData:
    if apply_device_injection:
        if (
            cutover_time <= mains_series.index[0]
            or cutover_time >= mains_series.index[-1]
        ):
            raise ValueError("cutover_time must lie strictly inside mains_series.")

        target_series = subtract_channels_in_window(
            mains_series,
            devices_hourly,
            device_meter_keys,
            window_start=mains_series.index[0],
            window_end=cutover_time,
        )
    else:
        target_series = mains_series

    return ScenarioData(
        target_series=target_series,
        coldstart_days=coldstart_days,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=value_implausible,
    )
