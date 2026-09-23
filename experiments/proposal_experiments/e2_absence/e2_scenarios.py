from collections.abc import Mapping

import pandas as pd
from src.pipeline.comparison_harness import ScenarioData

def build_ctx_scenarios(
    target_series: pd.Series,
    *,
    coldstart_days: int,
    decision_times: tuple[pd.Timestamp, ...],
    calendar_events: tuple[Mapping[str, object], ...],
    target_imputed: pd.Series | None = None,
    value_implausible: pd.Series | None = None,
) -> tuple[ScenarioData, ScenarioData]:
    ctx0 = ScenarioData(
        target_series=target_series,
        coldstart_days=coldstart_days,
        decision_times=decision_times,
        calendar_events=(),
        calendar_source_available=False,
        calendar_source="none",
        target_imputed=target_imputed,
        value_implausible=value_implausible,
    )
    ctx1 = ScenarioData(
        target_series=target_series,
        coldstart_days=coldstart_days,
        decision_times=decision_times,
        calendar_events=calendar_events,
        calendar_source_available=True,
        calendar_source="user_calendar",
        target_imputed=target_imputed,
        value_implausible=value_implausible,
    )

    return ctx0, ctx1