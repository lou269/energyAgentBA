from dataclasses import replace

import pandas as pd

from experiments.common.scenarios import (
    add_constant_step,
    add_linear_ramp,
    add_single_day_peak,
    add_stuck_value,
    build_decision_times,
    crop_history_for_coldstart,
    load_split_bounds,
    load_target,
    scale_from,
    scenario_without_calendar,
)
from experiments.common.standard_config import (
    COLDSTART_DAYS,
    LOCAL_TIMEZONE,
    STANDARD_CONFIG,
)
from src.common.timestamps import local_day_hours, local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


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
    # Stärke steckt im Namen: step_30 = +30 W ab Cutover, ramp_28 = in 28 Tagen auf scale_factor, peak_6 = 6 Stunden Spitze,
    # level_250 = der ganze Cutover-Tag +250 W, Endung _down = Faktor nach unten (scaled_down, ramp_28_down)
    base = kind.removesuffix("_down")
    factor = (
        STANDARD_CONFIG.scale_factor_down
        if base != kind
        else STANDARD_CONFIG.scale_factor
    )
    name, _, strength = base.partition("_")

    if kind == "control":
        return history
    if kind == "step":
        return add_constant_step(
            history, cutover_time, STANDARD_CONFIG.step_injection_w
        )
    if name == "step":
        return add_constant_step(history, cutover_time, float(strength))
    if base == "scaled":
        return scale_from(history, cutover_time, factor)
    if name == "ramp":
        return add_linear_ramp(history, cutover_time, days=int(strength), factor=factor)
    if name == "peak":
        return add_single_day_peak(
            history,
            cutover_time + pd.Timedelta(hours=STANDARD_CONFIG.peak_start_hour),
            hours=int(strength) if strength else STANDARD_CONFIG.peak_hours,
            extra_w=STANDARD_CONFIG.peak_extra_w,
        )
    if kind == "stuck":
        return add_stuck_value(history, cutover_time, hours=STANDARD_CONFIG.stuck_hours)
    if name == "level":
        # gleichmäßig über den Tag, die Schwankung im Tag (daily) bleibt, nur das Tagesmittel (weekday) steigt
        return add_single_day_peak(
            history,
            cutover_time,
            hours=len(local_day_hours(cutover_time, 1, "1h", LOCAL_TIMEZONE)),
            extra_w=float(strength),
        )

    raise ValueError(f"Unknown scenario kind: {kind}")
