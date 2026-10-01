# python -m pytest tests/unit/experiments/proactive_cycle/test_retransformation_factor.py -v

import numpy as np
import pandas as pd
import pytest

from experiments.proactive_cycle.pc_outlook import day_mean_retransformation_factor

TIMEZONE = "Europe/London"


def _history(start: str, end: str, sunday_w: float, other_w: float) -> pd.Series:
    index = pd.date_range(start, f"{end} 23:00", freq="1h", tz=TIMEZONE)
    power = np.where(index.dayofweek == 6, sunday_w, other_w)

    return pd.Series(power, index=index.tz_convert("UTC"))


def _factor(history: pd.Series, day: str) -> float | None:
    return day_mean_retransformation_factor(
        history,
        pd.Timestamp(day, tz=TIMEZONE),
        reference_window_rolling_days=60,
        min_weekday_reference_samples=4,
        local_timezone=TIMEZONE,
    )


def test_factor_of_a_flat_and_a_skewed_hour() -> None:
    flat = _history("2014-01-01", "2014-03-29", 500.0, 200.0)
    index = pd.date_range("2014-01-01", "2014-03-29 23:00", freq="1h", tz=TIMEZONE)
    day_number = (index.normalize() - index[0].normalize()).days
    # derselbe Wochentag wechselt zwischen 100 W und 400 W, Mittel 250 W, geometrisches Mittel 200 W
    skewed = pd.Series(
        np.where(day_number % 2 == 0, 100.0, 400.0), index=index.tz_convert("UTC")
    )

    assert _factor(flat, "2014-03-30") == pytest.approx(1.0)
    assert _factor(skewed, "2014-03-30") == pytest.approx(1.25, abs=0.1)
    assert _factor(flat.iloc[: 24 * 20], "2014-01-21") is None
