from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    add_days_since_cutover,
    merge_cycle_days,
    pair_with_control,
    spread_over_repeats,
    summarize_event_response,
)

PAIR_KEYS = ["cutover_date", "days_since_cutover"]
EVENT_KEYS = ["cutover_date", "kind"]

DRIFT_RESULT_COLUMNS = [
    "kind",
    "cutover_date",
    "decision_time",
    "classification",
    "anomaly_level",
    "dominant_scale",
    "sustained_drift",
    "alarm",
    "gate_open",
    "new_pattern",
    "reference_reset",
]


def read_drift_results(
    summary: pd.DataFrame, anomaly: pd.DataFrame, *, kind: str, cutover_date: str
) -> pd.DataFrame:
    results = merge_cycle_days(summary, anomaly).assign(
        kind=kind, cutover_date=cutover_date
    )

    return results[DRIFT_RESULT_COLUMNS]


@dataclass(frozen=True)
class RampSummary:
    detection: pd.DataFrame
    gate_open: pd.DataFrame


def summarize_ramp_response(results: pd.DataFrame) -> RampSummary:
    """Je Art und Cutover: erster Tag mit new_pattern, den der Kontrolllauf nicht hat (leer = still aufgenommen),
    und die Tage mit offenem Gate ohne Gegenstück im Kontrolllauf. An diesen Tagen würde SYS3 das LLM fragen
    """
    paired = pair_with_control(add_days_since_cutover(results), PAIR_KEYS)

    first_days = summarize_event_response(paired, EVENT_KEYS)
    detection = spread_over_repeats(
        first_days, ["kind"], "first_event_new_pattern_day", count_detected=True
    )
    cutovers = sorted(first_days["cutover_date"].unique())
    detection[cutovers] = detection[cutovers].astype("Int64")

    after_cutover = paired.loc[paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]
    gate_open_days = after_cutover.groupby(EVENT_KEYS, as_index=False).agg(
        gate_open_days=("event_gate_open", "sum")
    )

    return RampSummary(
        detection=detection,
        gate_open=spread_over_repeats(gate_open_days, ["kind"], "gate_open_days"),
    )
