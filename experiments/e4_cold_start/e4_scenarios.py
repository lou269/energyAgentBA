from dataclasses import replace

from experiments.common.scenarios import (
    crop_history_for_coldstart,
    load_target,
    local_day_window,
    scenario_without_calendar,
)
from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.common.standard_scenarios import build_kind_series
from experiments.e4_cold_start.e4_config import CLEAN_SCENARIO
from src.common.timestamps import local_calendar_range, local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def build_system_scenarios(
    start_date: str,
    coldstart_days: int,
    evaluation_days: int,
    *,
    injection_kinds: tuple[str, ...],
    injection_days: tuple[int, ...],
) -> dict[tuple[str, int | None], ScenarioData]:
    # für jede Kaltstart-Länge dieselben Entscheidungstage, nur Historie davor kürzer
    # je Lauf höchstens eine Injektion, sonst sickert sie in die Referenz der nächsten
    mains_series, target_imputed, value_implausible = load_target()

    start, end = local_day_window(start_date, evaluation_days)
    decision_times = tuple(local_calendar_range(start, 1, end, LOCAL_TIMEZONE))
    history = crop_history_for_coldstart(
        mains_series, decision_times[0], coldstart_days
    )
    clean = scenario_without_calendar(
        history, decision_times, coldstart_days, target_imputed, value_implausible
    )

    scenarios: dict[tuple[str, int | None], ScenarioData] = {
        (CLEAN_SCENARIO, None): clean
    }
    for kind in injection_kinds:
        for injection_day in injection_days:
            injection_time = local_midnight_utc(
                start_date, LOCAL_TIMEZONE, days_offset=injection_day
            )
            scenarios[(kind, injection_day)] = replace(
                clean, target_series=build_kind_series(history, injection_time, kind)
            )

    return scenarios
