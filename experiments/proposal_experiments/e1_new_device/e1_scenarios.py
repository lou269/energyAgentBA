import pandas as pd

from experiments.proposal_experiments.shared import subtract_channels_in_window
from src.pipeline.comparison_harness import ScenarioData


def build_device_scenario(
    mains_series: pd.Series,
    device_hourly: pd.Series,
    device_meter_key: str,
    *,
    cutover_time: pd.Timestamp,
    coldstart_hours: int,
    decision_times: tuple[pd.Timestamp, ...],
    target_imputed: pd.Series | None = None,
) -> ScenarioData:
    """Baut die E1-Zielreihe: vor cutover_time ist das echte Gerätesignal aus Mains herausgerechnet (Haushalt ohne das Gerät), 
    ab cutover_time bleibt Mains unverändert (Gerät real vorhanden)"""
    if cutover_time <= mains_series.index[0] or cutover_time >= mains_series.index[-1]:
        raise ValueError("cutover_time must lie strictly inside mains_series.")

    target_series = subtract_channels_in_window(
        mains_series,
        device_hourly.to_frame(name=device_meter_key),
        [device_meter_key],
        window_start=mains_series.index[0],
        window_end=cutover_time,
    )


    return ScenarioData(
        target_series=target_series,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
    )



