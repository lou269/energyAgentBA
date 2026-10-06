from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    add_days_since_cutover,
    summarize_cutover_response,
)
from experiments.common.standard_config import GOLDSTANDARD_EXPECTED, LOCAL_TIMEZONE
from src.common.timestamps import shift_local_days

RESULT_COLUMNS = [
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
    "explanation",
    "error",
    "day_error_w",
    "mae_w",
    "mape_pct",
]


def summarize_device_window(
    devices_hourly: pd.DataFrame,
    meter_keys: Sequence[str],
    mains: pd.Series,
    cutover_time: pd.Timestamp,
    days_after: int,
) -> dict[str, float]:
    """Gerät neben Mains: Leistung und Anteil an Mains in den days_after Tagen ab dem Cutover, Abdeckung des Gerätekanals davor und danach"""
    device = (
        devices_hourly[list(meter_keys)]
        .sum(axis=1, min_count=len(meter_keys))
        .reindex(mains.index)
    )
    before = mains.index < cutover_time
    after = (mains.index >= cutover_time) & (
        mains.index < shift_local_days(cutover_time, days_after, LOCAL_TIMEZONE)
    )

    return {
        "device_mean_w": device[after].mean(),
        "device_share_pct": device[after].sum() / mains[after].sum() * 100,
        "coverage_before_pct": device[before].notna().mean() * 100,
        "coverage_after_pct": device[after].notna().mean() * 100,
    }


@dataclass(frozen=True)
class E1Summary:
    response: pd.DataFrame
    events: pd.DataFrame


def summarize_e1(
    results: pd.DataFrame,
    *,
    reference_config: str,
    device_kinds: Sequence[str],
    target_classification: str,
) -> E1Summary:
    expected = {"control": GOLDSTANDARD_EXPECTED["control"]} | dict.fromkeys(
        device_kinds, target_classification
    )
    systems = add_days_since_cutover(
        results.loc[results["config"].ne(reference_config)]
    )
    happened = (
        systems["new_pattern"]
        | systems["adaption_action"].ne("none")
        | systems["error"].notna()
    )

    return E1Summary(
        response=summarize_cutover_response(results, reference_config, expected),
        events=systems.loc[
            happened,
            [
                "cutover_date",
                "kind",
                "config",
                "days_since_cutover",
                "analyzed_day",
                "classification",
                "adaption_action",
                "explanation",
                "error",
            ],
        ].sort_values(["cutover_date", "kind", "config", "days_since_cutover"]),
    )
