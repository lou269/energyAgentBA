# python -m pytest tests/unit/forecasting/test_prophet_model.py -v

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.forecasting.prophet_model import (
    _prepare_prophet_data,
    build_prophet_forecast,
    fit_prophet_model,
)


def _history(
    values: list[float],
    start: str = "2020-01-01"
) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)


def _fit(
    history: pd.Series,
    country_holidays: str | None = None,
    local_timezone: str = "UTC",
    log_transform: bool = False,
):
    return fit_prophet_model(
        history,
        growth="linear",
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
        country_holidays=country_holidays,
        local_timezone=local_timezone,
        log_transform=log_transform,
        interval_width=0.8,
        uncertainty_samples=200,
    )


def test_clipping_applies_to_interval_bounds_not_only_the_point_forecast() -> None:
    np.random.seed(0)
    # niedrige Grundlast mit gelegentlichen Spitzen -> Prophet erzeugt reale negative untere Intervallgrenzen, obwohl Verbrauch physikalisch nie negativ sein kann
    history = _history([0.1, 0.1, 5.0, 0.1, 0.1, 0.1] * 10)
    model = _fit(history)
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=6, freq="1h", tz="UTC")

    unclipped = build_prophet_forecast(
        model, target_index, clip_negative_forecasts=False,
        history_end=history.index[-1], local_timezone="UTC", log_transform=False,
    )
    clipped = build_prophet_forecast(
        model, target_index, clip_negative_forecasts=True,
        history_end=history.index[-1], local_timezone="UTC", log_transform=False,
    )

    # Voraussetzung für einen aussagekräftigen Test: es müssen überhaupt negative Rohwerte auftreten, sonst würde das Clipping nichts prüfen
    assert (unclipped["y_lower"] < 0).any()

    assert (clipped["y_pred"] >= 0).all()
    assert (clipped["y_lower"] >= 0).all()
    assert (clipped["y_upper"] >= 0).all()


def test_country_holidays_are_added_to_the_model_when_configured() -> None:
    history = _history([0.1, 0.1, 5.0, 0.1, 0.1, 0.1] * 10)

    without_holidays = _fit(history, country_holidays=None)
    with_holidays = _fit(history, country_holidays="UK")

    assert without_holidays.train_holiday_names is None
    assert with_holidays.train_holiday_names is not None
    assert len(with_holidays.train_holiday_names) > 0


def test_forecast_rejects_history_at_or_after_the_forecast_origin() -> None:
    history = _history([1.0, 2.0, 3.0, 4.0])
    model = _fit(history)
    # Zielzeitpunkt liegt nicht nach dem Ende der Trainingshistorie -> Kausalitätsverletzung
    overlapping_target = pd.date_range(history.index[-1], periods=1, freq="1h", tz="UTC")

    with pytest.raises(ValueError, match="at or after the forecast origin"):
        build_prophet_forecast(
            model, overlapping_target, clip_negative_forecasts=False,
            history_end=history.index[-1], local_timezone="UTC", log_transform=False,
        )


def test_ds_uses_local_time_so_dst_does_not_shift_the_daily_pattern() -> None:
    # 12:00 UTC an einem Sommer- und einem Wintertag -> in London 13:00 BST bzw. 12:00 GMT.
    # Mit UTC als ds-Zeitzone wäre "dieselbe" Stunde an beiden Tagen künstlich verschieden.
    history = pd.Series(
        [1.0, 2.0],
        index=pd.DatetimeIndex(
            ["2020-06-15 12:00:00+00:00", "2020-12-15 12:00:00+00:00"], tz="UTC"
        ),
    )

    prepared = _prepare_prophet_data(history, "Europe/London", log_transform=False)

    assert prepared["ds"].iloc[0].hour == 13
    assert prepared["ds"].iloc[1].hour == 12


def test_log_transform_rejects_non_positive_history() -> None:
    history = _history([1.0, 0.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="strictly positive"):
        _prepare_prophet_data(history, "UTC", log_transform=True)


def test_log_transform_forecast_stays_positive_and_matches_scale() -> None:
    np.random.seed(0)
    # log-normal-artige Werte um 100 mit gelegentlichen Spitzen -> realistischer als reine Konstante
    history = _history([100.0, 90.0, 400.0, 95.0, 105.0, 98.0] * 10)
    model = _fit(history, log_transform=True)
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=6, freq="1h", tz="UTC")

    forecast = build_prophet_forecast(
        model, target_index, clip_negative_forecasts=False,
        history_end=history.index[-1], local_timezone="UTC", log_transform=True,
    )

    # exp() ist nie negativ -> das bekannte negative-Intervallgrenzen-Problem entfällt strukturell
    assert (forecast["y_lower"] >= 0).all()
    # Rücktransformation muss in der Größenordnung der Eingabewerte liegen, nicht im Log-Raum stecken bleiben
    assert forecast["y_pred"].between(10, 1000).all()