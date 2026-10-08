from experiments.common.standard_scenarios import (
    build_event_series_scenario,
    build_standard_scenarios,
)
from src.pipeline.comparison_harness import ScenarioData


def build_e3_scenarios(
    cutover_date: str,
    events: tuple[tuple[int, str], ...],
) -> dict[str, ScenarioData]:
    # beide Reihen mit denselben decision_times, bis zum ersten Ereignis Tag für Tag gleich
    control = build_standard_scenarios(cutover_date, ("control",))["control"]

    return {
        "control": control,
        "events": build_event_series_scenario(control, cutover_date, events),
    }
