from collections.abc import Mapping

from experiments.common.standard_scenarios import (
    build_event_series_scenario,
    build_standard_scenarios,
)
from src.pipeline.comparison_harness import ScenarioData


def build_e3_scenarios(
    cutover_date: str, event_series: Mapping[str, tuple[tuple[int, str], ...]]
) -> dict[str, ScenarioData]:
    # Reihen mit denselben decision_times, bis zum ersten Ereignis Tag für Tag gleich
    control = build_standard_scenarios(cutover_date, ("control",))["control"]
    scenarios = {"control": control}
    for series, events in event_series.items():
        scenarios[series] = build_event_series_scenario(control, cutover_date, events)

    return scenarios
