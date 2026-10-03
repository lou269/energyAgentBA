from dataclasses import replace

import pandas as pd

from experiments.common.scenarios import add_stuck_flags
from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.common.standard_scenarios import (
    build_kind_series,
    build_standard_scenarios,
)
from src.common.timestamps import local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def add_events(
    series: pd.Series, cutover_date: str, events: tuple[tuple[int, str], ...]
) -> pd.Series:
    for day, kind in events:
        event_time = local_midnight_utc(cutover_date, LOCAL_TIMEZONE, days_offset=day)
        series = build_kind_series(series, event_time, kind)

    return series


def build_e5_scenarios(
    cutover_date: str,
    events: tuple[tuple[int, str], ...],
    *,
    margin_before_days: int,
    margin_after_days: int,
) -> dict[str, ScenarioData]:
    # beide Reihen mit denselben decision_times, bis zum ersten Ereignis Tag für Tag gleich
    control = build_standard_scenarios(
        cutover_date,
        ("control",),
        margin_before_days=margin_before_days,
        margin_after_days=margin_after_days,
    )["control"]

    event_series = add_events(control.target_series, cutover_date, events)

    return {
        "control": control,
        "events": replace(
            control,
            target_series=event_series,
            value_implausible=add_stuck_flags(
                event_series, control.target_imputed, control.value_implausible
            ),
        ),
    }
