from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    add_days_since_cutover,
    compare_mae_to_reference_after_reset,
    pair_with_control,
    summarize_event_response,
)
from experiments.common.standard_config import GOLDSTANDARD_EXPECTED, LOCAL_TIMEZONE
from src.common.timestamps import local_midnight_utc

# gepaart wird je System, nach einem Reset laufen Regel und LLM auseinander
PAIR_KEYS = ["config", "cutover_date", "days_since_cutover"]
EVENT_KEYS = ["config", "cutover_date", "kind"]

DRIFT_RESULT_COLUMNS = [
    "config",
    "kind",
    "cutover_date",
    "decision_time",
    "analyzed_day",
    "classification",
    "anomaly_level",
    "dominant_scale",
    "sustained_drift",
    "alarm",
    "gate_open",
    "new_pattern",
    "reference_reset",
    "adaption_action",
    "mae_w",
]


@dataclass(frozen=True)
class DriftSummary:
    response: pd.DataFrame


def summarize_drift_response(
    results: pd.DataFrame, reference_config: str
) -> DriftSummary:
    systems = results.loc[results["config"].ne(reference_config)]
    paired = pair_with_control(add_days_since_cutover(systems), PAIR_KEYS)

    after_cutover = paired.loc[paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]
    gate_open = after_cutover.groupby(EVENT_KEYS, as_index=False).agg(
        gate_open_days=("event_gate_open", "sum")
    )

    after_reset = pd.concat(
        [
            compare_mae_to_reference_after_reset(
                scenario,
                local_midnight_utc(str(cutover_date), LOCAL_TIMEZONE),
                reference_config,
            ).assign(kind=kind, cutover_date=str(cutover_date))  # type: ignore
            for (kind, cutover_date), scenario in results.groupby(
                ["kind", "cutover_date"]
            )
        ],
        ignore_index=True,
    )

    response = (
        systems[EVENT_KEYS]
        .drop_duplicates()
        .merge(summarize_event_response(paired, EVENT_KEYS), how="left")
        .merge(gate_open, how="left")
        .merge(
            after_reset[EVENT_KEYS + ["reset_forecast_day", "mean_delta"]],
            how="left",
        )
    )
    response.insert(3, "expected", response["kind"].map(GOLDSTANDARD_EXPECTED))
    counts = ["first_event_new_pattern_day", "gate_open_days", "reset_forecast_day"]
    response[counts] = response[counts].astype("Int64")

    return DriftSummary(response=response)
