# python -m pytest tests/unit/experiments/e4_cold_start -v

import numpy as np
import pandas as pd
import pytest

from experiments.common.evaluation import (
    SCALE_VALUE_COLUMNS,
    SCALE_SUSTAINED_COLUMNS,
)
from experiments.e4_cold_start.e4_evaluation import (
    E4Summary,
    find_settling_day,
    summarize_e4,
)
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


def _forecast(coldstart_days: int, model_id: str, errors: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "start_date": START_DATE,
            "coldstart_days": coldstart_days,
            "model_id": model_id,
            "forecast_origin": _decision_times(len(errors)),
            "day_error_w": errors,
            "mae_w": errors,
            "mape_pct": [value / 10 for value in errors],
        }
    )


def _system(
    coldstart_days: int,
    classifications: list[str],
    *,
    scenario: str = "clean",
    injection_day: int | None = None,
    weekday_scores: list[float] | None = None,
) -> pd.DataFrame:
    days = len(classifications)
    frame = pd.DataFrame(
        {
            "start_date": START_DATE,
            "coldstart_days": coldstart_days,
            "scenario": scenario,
            "injection_day": injection_day,
            "decision_time": _decision_times(days),
            "analyzed_day": "",
            "classification": classifications,
            "reference_reset": [value == "new_pattern" for value in classifications],
            "gate_open": [value != "normal" for value in classifications],
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


def _summary() -> E4Summary:
    forecast_metrics = pd.concat(
        [
            _forecast(7, "B2", [200.0, 200.0, 200.0, 200.0]),
            _forecast(7, "C3_60", [160.0, 150.0, 120.0, 120.0]),
            _forecast(7, "C1", [160.0, 170.0, 180.0, 190.0]),
            _forecast(60, "B2", [200.0, 200.0, 200.0, 200.0]),
            _forecast(60, "C3_60", [130.0, 130.0, 120.0, 120.0]),
            _forecast(60, "C1", [130.0, 140.0, 150.0, 160.0]),
        ],
        ignore_index=True,
    )
    system_results = pd.concat(
        [
            # sauber: kurz meldet an Tag 1, lang an Tag 3, low und unknown zählen nicht
            _system(
                7,
                ["normal", "peak", "low", "normal"],
                weekday_scores=[np.nan, np.nan, 0.5, 0.5],
            ),
            _system(60, ["normal", "normal", "unknown", "peak"]),
            # Spitze an Tag 1, eingeordnet an Tag 2: lang erkennt sie, kurz erst einen Tag später
            # und setzt an Tag 1 zurück, solange weekday noch fehlt
            _system(
                7,
                ["normal", "new_pattern", "normal", "peak"],
                scenario="peak",
                injection_day=1,
                weekday_scores=[np.nan, np.nan, 0.5, 0.5],
            ),
            _system(
                60,
                ["normal", "normal", "peak", "normal"],
                scenario="peak",
                injection_day=1,
            ),
        ],
        ignore_index=True,
    )

    return summarize_e4(
        forecast_metrics,
        system_results,
        adaptive_model_id="C3_60",
        static_model_id="C1",
        reference_model_id="B2",
        week_days=2,
        smoothing_days=2,
    )


def test_notifications_count_only_reported_classes_on_the_same_day() -> None:
    notifications = _summary().system.notifications

    assert notifications["only_shortest"].sum() == 1
    assert notifications["only_longest"].sum() == 1
    assert notifications.loc[notifications["only_shortest"], "week"].tolist() == [1]
    assert notifications.loc[notifications["only_longest"], "week"].tolist() == [2]


def test_injection_counts_only_the_day_after_the_injection_day() -> None:
    pairs = _summary().system.injection_pairs

    # kurz trifft erst an Tag 3, das zählt nicht mehr
    assert pairs.at[0, "detected_shortest"] == False  # noqa: E712
    assert pairs.at[0, "detected_longest"] == True  # noqa: E712
    assert pairs.at[0, "missed"] == True  # noqa: E712
    assert pairs.at[0, "week"] == 2


def test_extra_reset_before_all_scales_fails_the_criterion() -> None:
    summary = _summary()
    criteria = summary.criteria.set_index("check")

    assert len(summary.system.extra_resets) == 1
    assert criteria.at["extra_resets_before_all_scales", "value"] == 1
    assert not summary.works


def test_week_table_and_forecast_differences() -> None:
    summary = _summary()
    weeks = summary.weeks
    week_one = weeks.loc[weeks["week"].eq(1)].iloc[0]
    overall = summary.forecast.overall.set_index("coldstart_days")

    assert week_one["only_shortest"] == 1
    # Woche 1 = Tag 0 und 1: gegenüber der Baseline (160 + 150) / 2 - 200
    assert summary.forecast.weeks.at[0, "minus_reference_7"] == pytest.approx(-45.0)
    assert overall.at[7, "minus_static"] == pytest.approx(-(0 + 20 + 60 + 70) / 4)
    assert weeks["week"].isna().iloc[-1]
