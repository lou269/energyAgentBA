# python -m pytest tests/unit/experiments/e2_absence/test_e2_evaluation.py -v

import pandas as pd

from experiments.e2_absence.e2_evaluation import (
    PRECHECK_ANOMALY_COLUMNS,
    summarize_gate_precheck,
)
from src.common.timestamps import local_midnight_utc

TIMEZONE = "Europe/London"
WINDOW_START = local_midnight_utc("2013-09-14", TIMEZONE)
WINDOW_END = local_midnight_utc("2013-09-28", TIMEZONE)

# Tag vor dem Urlaub, Urlaubstag 0 (Gate zu), 1 (Einzeltag), 8 (Drift und Reset), erster Tag nach der Rückkehr
DAYS = ["2013-09-13", "2013-09-14", "2013-09-15", "2013-09-22", "2013-09-28"]


def _precheck_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    comparison = pd.DataFrame(
        {
            "analyzed_day": DAYS,
            "config": "SYS2",
            "classification": ["normal", "normal", "low", "new_pattern", "peak"],
            "adaption_action": [
                "none",
                "none",
                "none",
                "advance_history_start",
                "none",
            ],
            "mae_w": [50.0, 60.0, 70.0, 80.0, 90.0],
        }
    )
    anomaly = pd.DataFrame(
        {column: float("nan") for column in PRECHECK_ANOMALY_COLUMNS},
        index=range(len(DAYS)),
    )
    anomaly["config"] = "SYS2"
    anomaly["analyzed_day"] = DAYS
    anomaly["anomaly_level"] = ["normal", "normal", "unusual", "normal", "unusual"]
    anomaly["sustained_drift"] = [False, False, False, True, False]

    return comparison, anomaly


def test_summarize_gate_precheck_splits_gate_paths_by_phase() -> None:
    comparison, anomaly = _precheck_inputs()

    summary = summarize_gate_precheck(
        comparison, anomaly, window_start=WINDOW_START, window_end=WINDOW_END
    )

    phases = summary.phases.set_index("phase")
    assert phases.loc["absence", "days"] == 3
    assert phases.loc["absence", "single_day_gate_days"] == 1
    assert phases.loc["absence", "drift_gate_days"] == 1
    assert phases.loc["absence", "reset_days"] == 1
    assert phases.loc["absence", "notification_days"] == 2
    assert phases.loc["after_return", "peak_days"] == 1

    first = summary.first_days.set_index("config").loc["SYS2"]
    assert (
        first["first_gate_open_day"],
        first["first_drift_day"],
        first["first_reset_day"],
    ) == (1, 8, 8)
    assert summary.days_from_absence["absence_day"].tolist() == [0, 1, 8, 14]
