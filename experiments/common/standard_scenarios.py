from dataclasses import replace

from experiments.common.scenarios import (
    add_constant_step,
    build_decision_times,
    crop_history_for_coldstart,
    load_target,
    scale_from,
    scenario_without_calendar,
)
from experiments.common.standard_config import LOCAL_TIMEZONE, STANDARD_CONFIG
from src.common.timestamps import local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def build_standard_scenarios(
    cutover_date: str, kinds: tuple[str, ...]
) -> dict[str, ScenarioData]:
    # Szenarien für einen Cutover, alle mit denselben decision_times, also tageweise gepaart auswertbar
    mains_series, target_imputed, value_implausible = load_target()

    # lokale Mitternacht, damit der Cutover genau auf eine Tagesgrenze der Anomalieerkennung fällt
    cutover_time = local_midnight_utc(cutover_date, LOCAL_TIMEZONE)

    decision_times = build_decision_times(
        cutover_time,
        cutover_time,
        margin_before_days=STANDARD_CONFIG.monitoring_before_cutover_days,
        margin_after_days=STANDARD_CONFIG.margin_after_days,
    )
    history = crop_history_for_coldstart(mains_series, decision_times[0])
    control = scenario_without_calendar(
        history, decision_times, target_imputed, value_implausible
    )

    # control unverändert, step = Dauerlast ab Cutover, scaled = alles ab Cutover mal scale_factor
    series_by_kind = {
        "control": history,
        "step": add_constant_step(
            history, cutover_time, STANDARD_CONFIG.step_injection_w
        ),
        "scaled": scale_from(history, cutover_time, STANDARD_CONFIG.scale_factor),
    }

    return {
        kind: replace(control, target_series=series_by_kind[kind]) for kind in kinds
    }
