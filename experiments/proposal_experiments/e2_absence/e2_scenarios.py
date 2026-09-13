from collections.abc import Mapping, Sequence

import pandas as pd

from src.pipeline.comparison_harness import ScenarioData


def subtract_presence_channels(
    mains: pd.Series,
    appliance_data_hourly: pd.DataFrame,
    meter_keys: Sequence[str],
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.Series:
    """Zieht Summe der echten Gerätesignale von Mains ab - nur innerhalb [window_start, window_end), außerhalb bleibt die Reihe unverändert"""
    if not meter_keys:
        raise ValueError("meter_keys must not be empty.")

    missing = set(meter_keys) - set(appliance_data_hourly.columns)
    if missing:
        raise ValueError(f"appliance_data_hourly is missing columns: {', '.join(sorted(missing))}")

    window_mask = (mains.index >= window_start) & (mains.index < window_end)
    window_index = mains.index[window_mask]

    combined_load = (
        appliance_data_hourly.loc[:, meter_keys]
        .reindex(window_index)
        .fillna(0.0)
        .sum(axis=1)
    )

    adjusted = mains.copy()
    adjusted.loc[window_index] = (adjusted.loc[window_index] - combined_load).clip(lower=0.0)

    return adjusted


def build_ctx_scenarios(
    target_series: pd.Series,
    *,
    coldstart_hours: int,
    decision_times: tuple[pd.Timestamp, ...],
    calendar_events: tuple[Mapping[str, object], ...],
    target_imputed: pd.Series | None = None,
) -> tuple[ScenarioData, ScenarioData]:
    ctx0 = ScenarioData(
        target_series=target_series,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
    )
    ctx1 = ScenarioData(
        target_series=target_series,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=calendar_events,
        calendar_source_available=True,
        calendar_source="user_calendar",
        target_imputed=target_imputed,
    )

    return ctx0, ctx1