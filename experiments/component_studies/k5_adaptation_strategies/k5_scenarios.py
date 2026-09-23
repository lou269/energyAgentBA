from dataclasses import replace

from experiments.proposal_experiments.shared import scale_from
from src.common.timestamps import local_midnight_utc
from src.pipeline.comparison_harness import ScenarioData


def add_scaled_scenario(
    scenarios: dict[str, ScenarioData],
    *,
    cutover_date: str,
    scale_factor: float,
    local_timezone: str,
) -> dict[str, ScenarioData]:
    # gleiche Entscheidungstage wie control/step aus K3, nur ab dem Cutover alles mal scale_factor
    control = scenarios["control"]
    cutover_time = local_midnight_utc(cutover_date, local_timezone)
    scenarios["scaled"] = replace(control, target_series=scale_from(control.target_series, cutover_time, scale_factor))

    return scenarios