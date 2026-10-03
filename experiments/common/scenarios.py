from collections.abc import Sequence
from functools import cache

import pandas as pd

from experiments.common.standard_config import (
    HOURLY_SAMPLE_PERIOD_HOURS,
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STUCK_VALUE_MIN_HOURS,
)
from src.common.target_series import read_preprocessed_target
from src.common.timestamps import (
    local_calendar_range,
    local_midnight_utc,
    shift_local_days,
)
from src.pipeline.comparison_harness import ScenarioData
from src.preprocessing.plausibility_check import flag_implausible_values


@cache
def load_target() -> tuple[pd.Series, pd.Series, pd.Series]:
    # Mains, Imputationsmaske und Plausibilitätsflags aus der Vorverarbeitung, für alle Studien dieselben, nur einmal gelesen
    return read_preprocessed_target(PROJECT_CONFIG)


def build_decision_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    margin_before_days: int,
    margin_after_days: int,
) -> tuple[pd.Timestamp, ...]:
    start = shift_local_days(window_start, -margin_before_days, LOCAL_TIMEZONE)
    end = shift_local_days(window_end, margin_after_days, LOCAL_TIMEZONE)

    return tuple(local_calendar_range(start, 1, end, LOCAL_TIMEZONE))


def crop_history_for_coldstart(
    series: pd.Series, first_decision_time: pd.Timestamp, coldstart_days: int
) -> pd.Series:
    # der Tag vor first_decision_time kommt im ersten Zyklus als new_observations und zählt zu den coldstart_days,
    # am ersten Entscheidungstag liegen also genau coldstart_days Tage vor, wie nach einem Reset
    crop_start = shift_local_days(first_decision_time, -coldstart_days, LOCAL_TIMEZONE)
    return series.loc[crop_start:]


def scenario_without_calendar(
    target_series: pd.Series,
    decision_times: tuple[pd.Timestamp, ...],
    coldstart_days: int,
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
) -> ScenarioData:
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


def local_day_window(start_date: str, days: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    # end ist die letzte Stunde des letzten Tages, passt also direkt in .loc
    start = local_midnight_utc(start_date, LOCAL_TIMEZONE)
    end = local_midnight_utc(
        start_date, LOCAL_TIMEZONE, days_offset=days
    ) - pd.Timedelta(hours=1)

    return start, end


def slice_history_window(
    target_series: pd.Series,
    target_imputed: pd.Series,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    history_days: int | None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    # history_days Tage Historie vor start, None = alles davor (K1 macro), ausgewertet wird start bis end inklusive
    history_start = (
        None
        if history_days is None
        else shift_local_days(start, -history_days, LOCAL_TIMEZONE)
    )
    history = target_series.loc[history_start : start - pd.Timedelta(hours=1)]

    return history, target_series.loc[start:end], target_imputed.loc[start:end]


def subtract_channels_in_window(
    mains: pd.Series,
    appliance_data_hourly: pd.DataFrame,
    meter_keys: Sequence[str],
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.Series:
    window_mask = (mains.index >= window_start) & (mains.index < window_end)
    window_index = mains.index[window_mask]

    combined_load = (
        appliance_data_hourly.loc[:, meter_keys]
        .reindex(window_index)
        .fillna(0.0)
        .sum(axis=1)
    )

    adjusted = mains.copy()
    adjusted.loc[window_index] = (adjusted.loc[window_index] - combined_load).clip(
        lower=0.0
    )

    return adjusted


def add_constant_step(
    series: pd.Series, start: pd.Timestamp, watts: float
) -> pd.Series:
    stepped = series.copy()
    stepped.loc[stepped.index >= start] += watts

    return stepped


def scale_from(series: pd.Series, start: pd.Timestamp, factor: float) -> pd.Series:
    scaled = series.copy()
    scaled.loc[scaled.index >= start] *= factor

    return scaled


def add_linear_ramp(
    series: pd.Series, start: pd.Timestamp, *, days: int, factor: float
) -> pd.Series:
    # Faktor steigt stündlich linear von 1 auf factor und bleibt nach days Tagen dort, vor start bleibt er 1
    ramped = series.copy()
    elapsed = ramped.index.to_series() - start
    progress = (elapsed / pd.Timedelta(days=days)).clip(0.0, 1.0)
    ramped *= 1 + (factor - 1) * progress.to_numpy()

    return ramped


def add_single_day_peak(
    series: pd.Series, start: pd.Timestamp, *, hours: int, extra_w: float
) -> pd.Series:
    peaked = series.copy()
    in_peak = (peaked.index >= start) & (
        peaked.index < start + pd.Timedelta(hours=hours)
    )
    peaked.loc[in_peak] += extra_w

    return peaked


def add_stuck_value(series: pd.Series, start: pd.Timestamp, *, hours: int) -> pd.Series:
    # der letzte Wert vor start bleibt hängen
    stuck = series.copy()
    in_stuck = (stuck.index >= start) & (
        stuck.index < start + pd.Timedelta(hours=hours)
    )
    stuck.loc[in_stuck] = series.loc[start - pd.Timedelta(hours=1)]

    return stuck


def add_stuck_flags(
    series: pd.Series, imputed: pd.Series, implausible: pd.Series
) -> pd.Series:
    # die Flags aus der Vorverarbeitung kennen eingebaute Festhänger nicht, aufgefüllte Stunden zählen nicht als Messwert
    return implausible | flag_implausible_values(
        series.where(imputed.eq(False)),
        stuck_value_min_hours=STUCK_VALUE_MIN_HOURS,
        sample_period_hours=HOURLY_SAMPLE_PERIOD_HOURS,
    )
