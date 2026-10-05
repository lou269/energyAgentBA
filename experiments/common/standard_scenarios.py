from dataclasses import replace

import pandas as pd

from experiments.common.scenarios import (
    build_decision_times,
    crop_history_for_coldstart,
    load_split_bounds,
    load_target,
    scenario_without_calendar,
)
from experiments.common.standard_config import (
    COLDSTART_DAYS,
    HOURLY_SAMPLE_PERIOD_HOURS,
    LOCAL_TIMEZONE,
    STANDARD_CONFIG,
    STUCK_VALUE_MIN_HOURS,
)
from src.common.timestamps import local_day_hours, local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData
from src.preprocessing.plausibility_check import flag_implausible_values


def build_standard_scenarios(
    cutover_date: str,
    kinds: tuple[str, ...],
    *,
    split: str = STANDARD_CONFIG.split,
    margin_before_days: int = STANDARD_CONFIG.monitoring_before_cutover_days,
    margin_after_days: int = STANDARD_CONFIG.margin_after_days,
) -> dict[str, ScenarioData]:
    # Szenarien für einen Cutover, alle mit denselben decision_times, also tageweise gepaart auswertbar
    mains_series, target_imputed, value_implausible = load_target(split)

    # lokale Mitternacht, damit der Cutover genau auf eine Tagesgrenze der Anomalieerkennung fällt
    cutover_time = local_midnight_utc(cutover_date, LOCAL_TIMEZONE)

    decision_times = build_decision_times(
        cutover_time,
        cutover_time,
        margin_before_days=margin_before_days,
        margin_after_days=margin_after_days,
    )
    history = crop_history_for_coldstart(
        mains_series, decision_times, COLDSTART_DAYS, load_split_bounds(split)
    )
    control = scenario_without_calendar(
        history, decision_times, COLDSTART_DAYS, target_imputed, value_implausible
    )

    return {
        kind: replace(
            control, target_series=build_kind_series(history, cutover_time, kind)
        )
        for kind in kinds
    }


def build_kind_series(
    history: pd.Series, cutover_time: pd.Timestamp, kind: str
) -> pd.Series:
    # Stärken nur aus STANDARD_CONFIG, im Namen steht keine
    config = STANDARD_CONFIG
    evening = cutover_time + pd.Timedelta(hours=config.peak_start_hour)
    ramps = {
        "ramp_28": (config.ramp_fast_days, config.scale_factor),
        "ramp_56": (config.ramp_slow_days, config.scale_factor),
        "ramp_28_down": (config.ramp_fast_days, config.scale_factor_down),
        "ramp_56_down": (config.ramp_slow_days, config.scale_factor_down),
    }

    if kind == "control":
        return history
    if kind == "scaled":
        return scale_from(history, cutover_time, config.scale_factor)
    if kind == "scaled_strong":
        return scale_from(history, cutover_time, config.strong_scale_factor)
    if kind in ramps:
        days, factor = ramps[kind]
        return add_linear_ramp(history, cutover_time, days=days, factor=factor)
    if kind == "peak":
        return add_single_day_peak(
            history, evening, hours=config.peak_hours, extra_w=config.peak_extra_w
        )
    if kind == "peak_strong":
        return add_single_day_peak(
            history,
            evening,
            hours=config.peak_hours,
            extra_w=config.strong_peak_extra_w,
        )
    if kind == "level":
        # gleichmäßig über den Tag, die Schwankung im Tag (daily) bleibt, nur das Tagesmittel (weekday) steigt
        return add_single_day_peak(
            history,
            cutover_time,
            hours=len(local_day_hours(cutover_time, 1, "1h", LOCAL_TIMEZONE)),
            extra_w=config.level_extra_w,
        )
    if kind == "stuck":
        return add_stuck_value(history, cutover_time, hours=config.stuck_hours)

    raise ValueError(f"Unknown scenario kind: {kind}")


def scale_from(series: pd.Series, start: pd.Timestamp, factor: float) -> pd.Series:
    scaled = series.copy()
    scaled.loc[scaled.index >= start] *= factor

    return scaled


def add_linear_ramp(
    series: pd.Series, start: pd.Timestamp, *, days: int, factor: float
) -> pd.Series:
    # Faktor steigt stündlich linear von 1 auf factor und bleibt nach days Tagen dort
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
