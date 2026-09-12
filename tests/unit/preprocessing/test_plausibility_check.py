# python -m pytest tests/unit/preprocessing/test_plausibility_check.py -v

from __future__ import annotations

import pandas as pd

from src.common.column_naming import plausibility_column
from src.preprocessing.plausibility_check import build_plausibility_flags

IMPLAUSIBLE = plausibility_column("m1")


def _frame(
    index: pd.DatetimeIndex, 
    values: list[float | None], 
    column: str = "m1"
) -> pd.DataFrame:
    return pd.DataFrame({column: values}, index=index)


def _quality(
    index: pd.DatetimeIndex, 
    coverage: list[bool], 
    column: str = "m1"
) -> pd.DataFrame:
    return pd.DataFrame({f"{column}_coverage_mask": coverage}, index=index)


def test_negative_value_is_implausible() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="1h")
    data = _frame(index, [10.0, -5.0, 12.0])
    quality = _quality(index, [True, True, True])

    flags = build_plausibility_flags(data, quality, stuck_value_min_hours=4, sample_period_hours=1.0, resolution="hourly")

    assert flags[IMPLAUSIBLE].tolist() == [False, True, False]


def test_stuck_value_flagged_once_streak_reaches_threshold() -> None:
    index = pd.date_range("2020-01-01", periods=6, freq="1h")
    data = _frame(index, [10.0, 10.0, 10.0, 10.0, 10.0, 11.0])
    quality = _quality(index, [True] * 6)

    flags = build_plausibility_flags(data, quality, stuck_value_min_hours=3, sample_period_hours=1.0, resolution="hourly")

    assert flags[IMPLAUSIBLE].tolist() == [False, False, False, True, True, False]


def test_stuck_value_below_threshold_is_not_flagged() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="1h")
    data = _frame(index, [10.0, 10.0, 10.0])
    quality = _quality(index, [True, True, True])

    flags = build_plausibility_flags(data, quality, stuck_value_min_hours=5, sample_period_hours=1.0, resolution="hourly")

    assert not flags[IMPLAUSIBLE].any()


def test_missing_value_is_not_flagged() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="1h")
    data = _frame(index, [10.0, None, 10.0])
    quality = _quality(index, [True, False, True])

    flags = build_plausibility_flags(data, quality, stuck_value_min_hours=1, sample_period_hours=1.0, resolution="hourly")

    assert not flags[IMPLAUSIBLE].any()


def test_low_quality_value_is_masked_and_not_flagged() -> None:
    index = pd.date_range("2020-01-01", periods=2, freq="1h")
    data = _frame(index, [10.0, -5.0])
    quality = _quality(index, [True, False])

    flags = build_plausibility_flags(data, quality, stuck_value_min_hours=1, sample_period_hours=1.0, resolution="hourly")

    assert flags[IMPLAUSIBLE].tolist() == [False, False]


def test_stuck_streak_resets_after_change() -> None:
    index = pd.date_range("2020-01-01", periods=5, freq="1h")
    data = _frame(index, [10.0, 10.0, 10.0, 5.0, 5.0])
    quality = _quality(index, [True] * 5)

    flags = build_plausibility_flags(data, quality, stuck_value_min_hours=2, sample_period_hours=1.0, resolution="hourly")

    assert flags[IMPLAUSIBLE].tolist() == [False, False, True, False, False]