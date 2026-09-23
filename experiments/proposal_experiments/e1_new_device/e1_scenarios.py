from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.shared import subtract_channels_in_window
from src.common.column_naming import channel_data_column
from src.pipeline.comparison_harness import ScenarioData

DEVICE_HOURLY_FILE = Path(__file__).parent / "output" / "e1_device_hourly.csv"


def load_device_hourly(device_meter_key: str) -> pd.Series:
    device_data = pd.read_csv(DEVICE_HOURLY_FILE, parse_dates=["timestamp"], index_col="timestamp")

    return device_data[channel_data_column(device_meter_key, "hourly")]


def build_device_scenario(
    mains_series: pd.Series,
    device_hourly: pd.Series,
    device_meter_key: str,
    *,
    cutover_time: pd.Timestamp,
    coldstart_hours: int,
    decision_times: tuple[pd.Timestamp, ...],
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
    apply_device_injection: bool = True,
) -> ScenarioData:
    """Baut die E1-Zielreihe: vor cutover_time ist das echte Gerätesignal aus Mains herausgerechnet (Haushalt ohne das Gerät),
    ab cutover_time bleibt Mains unverändert (Gerät real vorhanden), apply_device_injection=False: Mains-Reihe als Kontrolllauf"""
    if apply_device_injection:
        if cutover_time <= mains_series.index[0] or cutover_time >= mains_series.index[-1]:
            raise ValueError("cutover_time must lie strictly inside mains_series.")

        target_series = subtract_channels_in_window(
            mains_series,
            device_hourly.to_frame(name=device_meter_key),
            [device_meter_key],
            window_start=mains_series.index[0],
            window_end=cutover_time,
        )
    else:
        target_series = mains_series

    return ScenarioData(
        target_series=target_series,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=value_implausible,
    )



