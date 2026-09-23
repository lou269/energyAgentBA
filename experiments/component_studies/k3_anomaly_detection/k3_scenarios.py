from dataclasses import replace

import pandas as pd

from experiments.proposal_experiments.shared import add_constant_step, build_decision_times, crop_history_for_coldstart
from src.common.timestamps import local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def build_k3_scenarios(
    mains_series: pd.Series,
    *,
    cutover_date: str,
    coldstart_hours: int,
    monitoring_before_cutover_days: int,
    margin_after_days: int,
    step_injection_w: float,
    local_timezone: str,
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
) -> dict[str, ScenarioData]:
    """control und step für einen Cutover, mit denselben decision_times, also tageweise gepaart auswertbar"""
    # lokale Mitternacht, damit der Cutover genau auf eine Tagesgrenze der Anomalieerkennung fällt
    cutover_time = local_midnight_utc(cutover_date, local_timezone)

    decision_times = build_decision_times(
        cutover_time, cutover_time,
        margin_before_days=monitoring_before_cutover_days, margin_after_days=margin_after_days,
        local_timezone=local_timezone,
    )
    history = crop_history_for_coldstart(
        mains_series, 
        coldstart_hours=coldstart_hours, 
        first_decision_time=decision_times[0]
    )

    control = ScenarioData(
        target_series=history,
        coldstart_hours=coldstart_hours,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=value_implausible,
    )

    return {
        "control": control,
        "step": replace(control, target_series=add_constant_step(history, cutover_time, step_injection_w)),
    }

