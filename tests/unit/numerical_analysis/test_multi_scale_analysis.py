# python -m pytest tests/unit/numerical_analysis/test_multi_scale_analysis.py -v

from collections.abc import Sequence

import pandas as pd
import pytest

from src.common.timestamps import local_day
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis


def _from_levels(day_levels: Sequence[float]) -> pd.Series:
    index = pd.date_range(
        "2020-01-01", periods=24 * len(day_levels), freq="1h", tz="UTC"
    )
    values = [level for level in day_levels for _ in range(24)]
    return pd.Series(values, index=index, name="p")


def _analyze(
    history: pd.Series,
    *,
    rolling_days: int = 60,
    long_term_window: int = 2,
    long_term_reference_days: int = 2,
    weekly_window_days: int = 2,
    min_weekday_samples: int = 1,
    min_power_w: float = 0.0,
    coverage: float = 1.0,
    robust: Sequence[str] = (),
    timezone: str = "UTC",
) -> pd.DataFrame:
    return build_multi_scale_analysis(
        history,
        analyzed_day=local_day(history.index[-1], timezone),
        reference_window_rolling_days=rolling_days,
        long_term_window=long_term_window,
        long_term_reference_days=long_term_reference_days,
        weekly_window_days=weekly_window_days,
        min_weekday_reference_samples=min_weekday_samples,
        min_longterm_reference_samples=1,
        min_reference_power_w=min_power_w,
        rolling_window_min_coverage=coverage,
        robust_scales=robust,
        local_timezone=timezone,
    )


def test_day_reference_window() -> None:
    levels = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 500.0]

    result = _analyze(_from_levels(levels), rolling_days=3)
    last = result.iloc[-1]

    # nur die drei Tage direkt davor, der Ausreißer selbst und ältere Tage zählen nicht
    assert result["daily_reference_value"].notna().sum() == 3
    assert pd.isna(last["daily_reference_value"])
    assert last["today_mean_expected"] == pytest.approx(170.0)
    assert last["today_mean"] == pytest.approx(500.0)


def test_day_reference_median() -> None:
    levels = [100.0, 102.0, 98.0, 400.0, 101.0, 500.0]

    mean_based = _analyze(_from_levels(levels), rolling_days=5).iloc[-1]
    median_based = _analyze(
        _from_levels(levels), rolling_days=5, robust=("daily",)
    ).iloc[-1]

    assert mean_based["today_mean_expected"] == pytest.approx(160.2)
    assert median_based["today_mean_expected"] == pytest.approx(101.0)


def test_weekday_expected() -> None:
    index = pd.date_range("2020-01-01", periods=21, freq="D", tz="UTC")
    levels = [100.0 + 10.0 * day.dayofweek for day in index]
    levels[-1] = 999.0
    history = _from_levels(levels)

    # der 21. Tag hat in den 20 Tagen davor genau zwei gleiche Wochentage
    enough = _analyze(history, min_weekday_samples=2).iloc[-1]
    too_few = _analyze(history, min_weekday_samples=3).iloc[-1]

    assert enough["weekday_expected"] == pytest.approx(
        100.0 + 10.0 * index[-1].dayofweek
    )
    assert pd.isna(too_few["weekday_expected"])


def test_weekly_reference_window() -> None:
    levels = [100.0 + 10.0 * day for day in range(12)]
    history = _from_levels(levels)
    daily_mean = history.resample("D").mean()

    result = _analyze(history, weekly_window_days=3, rolling_days=6)
    last = result.iloc[-1]

    # Beobachtung: letzte drei Tage inklusive dem bewerteten
    assert last["weekly_mean"] == pytest.approx(daily_mean.iloc[-3:].mean())

    # Referenz: Fenster Tag 3 bis 8, nur Dreitagesmittel, die ganz darin liegen (Ende Tag 5 bis 8)
    reference = result["weekly_reference_value"].dropna()
    assert list(reference.index) == list(daily_mean.index[5:9])
    assert last["weekly_mean_expected"] == pytest.approx(
        daily_mean.rolling(3).mean().iloc[5:9].mean()
    )


def test_long_term_reference_block() -> None:
    levels = [100.0 + 10.0 * day for day in range(12)]
    history = _from_levels(levels)
    daily_mean = history.resample("D").mean()

    last = _analyze(history, long_term_window=3, long_term_reference_days=4).iloc[-1]

    assert last["long_term_window_mean"] == pytest.approx(daily_mean.iloc[-3:].mean())
    assert last["long_term_expected"] == pytest.approx(daily_mean.iloc[-7:-3].mean())
    assert last["long_term_deviation_pct"] == pytest.approx(
        (200.0 - 165.0) / 165.0 * 100.0
    )


def test_deviation_pct_small_reference() -> None:
    history = _from_levels([100.0, 100.0, 100.0, 100.0, 150.0, 150.0])

    last = _analyze(history).iloc[-1]
    assert last["weekly_deviation_pct"] == pytest.approx(50.0)
    assert last["long_term_deviation_pct"] == pytest.approx(50.0)

    last = _analyze(history, min_power_w=200.0).iloc[-1]
    assert pd.isna(last["weekly_deviation_pct"])
    assert pd.isna(last["long_term_deviation_pct"])


def test_weekly_mean_tolerates_gap() -> None:
    levels = [100.0, 110.0, 120.0, 130.0, float("nan"), 150.0, 160.0, 170.0]
    history = _from_levels(levels)

    # Fenster Tag 4 bis 8 enthält den NaN-Tag, min_periods = ceil(5 * 0.8) = 4
    tolerant = _analyze(history, weekly_window_days=5, coverage=0.8).iloc[-1]
    strict = _analyze(history, weekly_window_days=5, coverage=1.0).iloc[-1]

    assert tolerant["weekly_mean"] == pytest.approx((130.0 + 150.0 + 160.0 + 170.0) / 4)
    assert pd.isna(strict["weekly_mean"])


def test_reference_window_across_dst() -> None:
    # 30.03.2014: Europe/London springt auf Sommerzeit, das Fenster liegt genau darüber
    index = pd.date_range("2014-03-01", "2014-04-20 12:00", freq="1h", tz="UTC")
    history = pd.Series(100.0, index=index, name="p")

    result = _analyze(history, rolling_days=30, timezone="Europe/London")
    reference = result["daily_reference_value"].dropna()

    assert len(reference) == 30
    assert reference.index[0].strftime("%Y-%m-%d") == "2014-03-21"
    assert reference.index[-1].strftime("%Y-%m-%d") == "2014-04-19"
