# python -m pytest tests/unit/forecasting/test_baselines.py -v

import pandas as pd
import pytest

from src.forecasting.baselines import (
    build_daily_naive_forecast,
    build_last_value_forecast,
    build_weekly_naive_forecast,
)


def _history(
    values: list[float], 
    start: str = "2020-01-01"
) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)


def test_last_value_forecast_repeats_final_observation() -> None:
    history = _history([10.0, 20.0, 30.0])
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=4, freq="1h", tz="UTC")

    forecast = build_last_value_forecast(history, target_index)

    assert (forecast == 30.0).all()


def test_daily_naive_uses_value_exactly_24h_before_each_target() -> None:
    # eindeutiges Muster über 48h, damit der 24h-Versatz konkret nachrechenbar ist
    history = _history([float(h) for h in range(48)])
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=3, freq="1h", tz="UTC")

    forecast = build_daily_naive_forecast(history, target_index)

    # Ziel = Stunde 48/49/50 -> 24h davor sind Stunde 24/25/26
    assert list(forecast.to_numpy()) == [24.0, 25.0, 26.0]


def test_weekly_naive_uses_value_exactly_168h_before_each_target() -> None:
    history = _history([float(h) for h in range(168)])
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=2, freq="1h", tz="UTC")

    forecast = build_weekly_naive_forecast(history, target_index)

    assert list(forecast.to_numpy()) == [0.0, 1.0]


def test_daily_naive_raises_when_reference_hour_is_missing() -> None:
    # Historie beginnt erst 10h vor dem Ziel -> die für den 24h-Versatz nötige Stunde fehlt
    # komplett (nicht nur NaN, sondern gar nicht im Index) -> auch das Zurückgehen findet nichts
    history = _history([1.0] * 10)
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=1, freq="1h", tz="UTC")

    with pytest.raises(ValueError, match="24h lag"):
        build_daily_naive_forecast(history, target_index)


def test_daily_naive_skips_an_excluded_day_and_uses_the_same_hour_further_back() -> None:
    # Tag 4 (Stunden 72-95) komplett als NaN ausgeschlossen, wie ein von der Preprocessing-Stufe verworfener Kalendertag
    values = [float(h) for h in range(96)]
    for h in range(72, 96):
        values[h] = float("nan")
    history = _history(values)
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=1, freq="1h", tz="UTC")

    forecast = build_daily_naive_forecast(history, target_index)

    # Ziel = Stunde 96, 24h davor (Stunde 72) ist NaN -> fällt auf Stunde 48 zurück (48h davor)
    assert list(forecast.to_numpy()) == [48.0]


def test_weekly_naive_skips_an_excluded_week_and_uses_the_same_weekday_hour_further_back() -> None:
    # Woche 3 (Stunden 336-503) komplett ausgeschlossen -> der direkte 168h-Referenzwert liegt darin
    values = [float(h) for h in range(504)]
    for h in range(336, 504):
        values[h] = float("nan")
    history = _history(values)
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=1, freq="1h", tz="UTC")

    forecast = build_weekly_naive_forecast(history, target_index)

    # Ziel = Stunde 504, 168h davor (Stunde 336) ist NaN -> fällt auf Stunde 168 zurück (336h davor)
    assert list(forecast.to_numpy()) == [168.0]


def test_baseline_rejects_history_overlapping_the_forecast_target() -> None:
    history = _history([1.0, 2.0, 3.0])
    # Historie reicht bis in den Zielzeitraum hinein -> Kausalitätsverletzung
    target_index = pd.date_range(history.index[-1], periods=2, freq="1h", tz="UTC")

    with pytest.raises(ValueError, match="before the first forecast target"):
        build_last_value_forecast(history, target_index)

