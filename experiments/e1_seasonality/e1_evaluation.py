from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import (
    SCALE_SUSTAINED_COLUMNS,
    summarize_cutover_response,
)
from experiments.common.standard_config import GOLDSTANDARD_EXPECTED

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
] + SCALE_SUSTAINED_COLUMNS


@dataclass(frozen=True)
class DriftSummary:
    response: pd.DataFrame


def summarize_drift_response(results: pd.DataFrame) -> DriftSummary:
    return DriftSummary(
        response=summarize_cutover_response(results, GOLDSTANDARD_EXPECTED)
    )
