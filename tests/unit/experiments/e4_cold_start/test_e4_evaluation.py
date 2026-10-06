# python -m pytest tests/unit/experiments/e4_cold_start -v

import numpy as np
import pandas as pd
import pytest

from experiments.common.evaluation import (
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
)
from experiments.e4_cold_start.e4_evaluation import find_settling_day, summarize_e4
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"
START_DATE = "2014-07-15"


def _decision_times(days: int) -> pd.DatetimeIndex:
    return local_calendar_range(
        local_midnight_utc(START_DATE, TIMEZONE),
        1,
        local_midnight_utc(START_DATE, TIMEZONE, days_offset=days - 1),
        TIMEZONE,
    )


def _forecast(coldstart_days: int, model_id: str, mae: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "start_date": START_DATE,
            "coldstart_days": coldstart_days,
            "model_id": model_id,
            "forecast_origin": _decision_times(len(mae)),
            "day_error_w": mae,
            "mae_w": mae,
            "mape_pct": [value / 10 for value in mae],
        }
    )


def _system(
    coldstart_days: int,
    gate_open: list[bool],
    *,
    scenario: str = "clean",
    injection_day: int | None = None,
    weekday_scores: list[float] | None = None,
    resets: list[bool] | None = None,
    classifications: list[str] | None = None,
) -> pd.DataFrame:
    days = len(gate_open)
    frame = pd.DataFrame(
        {
            "start_date": START_DATE,
            "coldstart_days": coldstart_days,
            "scenario": scenario,
            "injection_day": injection_day,
            "decision_time": _decision_times(days),
            "analyzed_day": "",
            "classification": classifications
            or ["peak" if gate else "normal" for gate in gate_open],
            "reference_reset": resets or [False] * days,
            "gate_open": gate_open,
            "dominant_scale": "daily",
            "explanation": "",
            "error": "",
            "day_error_w": [120.0] * days,
            "mae_w": [120.0] * days,
            "mape_pct": [12.0] * days,
        }
    )
    for column in SCALE_VALUE_COLUMNS:
        frame[column] = 0.5
    frame["weekday_score"] = weekday_scores or [0.5] * days
    for column in SCALE_SUSTAINED_COLUMNS:
        frame[column] = False

    return frame


def test_settling_needs_agreement_on_every_later_point() -> None:
    injections = pd.DataFrame(
        {
            "start_date": ["a", "a", "a", "a", "a", "a", "b", "b", "b"],
            "scenario": ["peak"] * 3 + ["level"] * 3 + ["peak"] * 3,
            "injection_day": [3, 10, 18] * 3,
            "missed": [True, False, False, False, False, True] + [False] * 3,
        }
    )

    settling = find_settling_day(
        injections,
        group_columns=["start_date", "scenario"],
        point_column="injection_day",
        deviation_column="missed",
        points=(3, 10, 18),
    )

    assert settling[("a", "peak")] == 10
    # nur der letzte Injektionstag weicht ab, danach gibt es keinen Beleg mehr
    assert np.isnan(settling[("a", "level")])
    assert settling[("b", "peak")] == 3


def test_summary_counts_resets_and_skill() -> None:
    forecast_metrics = pd.concat(
        [
            _forecast(7, "B2", [200.0, 200.0, 200.0, 200.0]),
            _forecast(7, "C3_30", [160.0, 150.0, 120.0, 120.0]),
            _forecast(7, "C1", [160.0, 170.0, 180.0, 190.0]),
            _forecast(60, "B2", [200.0, 200.0, 200.0, 200.0]),
            _forecast(60, "C3_30", [130.0, 130.0, 120.0, 120.0]),
            _forecast(60, "C1", [130.0, 140.0, 150.0, 160.0]),
        ],
        ignore_index=True,
    )
    system_results = pd.concat(
        [
            # Reset an Tag 1, weekday fehlt dort noch
            _system(
                7,
                [False, True, False, False],
                weekday_scores=[np.nan, np.nan, 0.5, 0.5],
                resets=[False, True, False, False],
                classifications=["unknown", "new_pattern", "normal", "normal"],
            ),
            _system(60, [False, False, False, False]),
            # Spitze an Tag 1, eingeordnet an Tag 2: CS60 erkennt sie, CS7 nicht
            _system(7, [False, False, False, False], scenario="peak", injection_day=1),
            _system(60, [False, False, True, False], scenario="peak", injection_day=1),
        ],
        ignore_index=True,
    )
    summary = summarize_e4(
        forecast_metrics,
        system_results,
        adaptive_model_id="C3_30",
        static_model_id="C1",
        reference_model_id="B2",
        single_day_scales=("daily", "weekday"),
        injection_days=(1,),
        window_edges_days=(2, 4),
        smoothing_days=2,
    )
    criteria = summary.criteria.set_index("check")

    assert criteria.at["resets_in_settling", "value"] == 1
    # Skill in 0-1: 1 - 155 / 200
    assert criteria.at["forecast_skill_first_window_pct", "value"] == pytest.approx(
        22.5
    )
    assert summary.system.injection_price.at[0, "missed"] == 1
