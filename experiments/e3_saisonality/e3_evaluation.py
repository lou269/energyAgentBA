from dataclasses import dataclass

import pandas as pd

from experiments.common.evaluation import summarize_cutover_response
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
    "reference_reset",
    "adaption_action",
    "day_error_w",
    "mae_w",
    "mape_pct",
]


@dataclass(frozen=True)
class DriftSummary:
    response: pd.DataFrame


def summarize_drift_response(
    results: pd.DataFrame, reference_config: str
) -> DriftSummary:
    """Je System, Cutover und Art: erwartete Klasse, Erkennung und Gate gegen den eigenen Kontrolllauf, erster Reset und Tagesfehler und MAE ab dort gegen reference_config"""
    return DriftSummary(
        response=summarize_cutover_response(
            results, reference_config, GOLDSTANDARD_EXPECTED
        )
    )
