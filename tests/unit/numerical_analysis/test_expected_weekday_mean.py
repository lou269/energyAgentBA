# python -m pytest tests/unit/numerical_analysis/test_expected_weekday_mean.py -v

import numpy as np
import pandas as pd
import pytest

from src.numerical_analysis.multi_scale_analysis import expected_weekday_mean

TIMEZONE = "Europe/London"


def _history(start: str, end: str, sunday_w: float, other_w: float) -> pd.Series:
    index = pd.date_range(start, f"{end} 23:00", freq="1h", tz=TIMEZONE)
    power = np.where(index.dayofweek == 6, sunday_w, other_w)

    return pd.Series(power, index=index.tz_convert("UTC"))


def _expected(history: pd.Series, day: str, robust: bool = False) -> float | None:
    return expected_weekday_mean(
        history,
        pd.Timestamp(day, tz=TIMEZONE),
        reference_window_rolling_days=60,
        min_weekday_reference_samples=4,
        robust=robust,
        local_timezone=TIMEZONE,
    )


def test_profile_of_the_forecast_weekday() -> None:
    history = _history("2014-01-01", "2014-03-29", 500.0, 200.0)

    # 30.03. ist ein Sonntag und der Tag der Umstellung auf Sommerzeit
    assert _expected(history, "2014-03-30") == pytest.approx(500.0)
    assert _expected(history, "2014-03-26") == pytest.approx(200.0)


def test_only_the_reference_window_counts() -> None:
    old = _history("2014-01-01", "2014-01-28", 900.0, 200.0)
    recent = _history("2014-01-29", "2014-03-29", 500.0, 200.0)

    assert _expected(pd.concat([old, recent]), "2014-03-30") == pytest.approx(500.0)


def test_too_few_weekdays() -> None:
    history = _history("2014-01-01", "2014-01-20", 500.0, 200.0)

    assert _expected(history, "2014-01-21") is None
