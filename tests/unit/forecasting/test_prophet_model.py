# python -m pytest tests/unit/forecasting/test_prophet_model.py -v

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.forecasting.prophet_model import build_prophet_forecast, fit_prophet_model


def _history(
    values: list[float], 
    start: str = "2020-01-01"
) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)


def _fit(
    history: pd.Series
):
    return fit_prophet_model(
        history,
        growth="linear",
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
        interval_width=0.8,
        uncertainty_samples=200,
    )


def test_clipping_applies_to_interval_bounds_not_only_the_point_forecast() -> None:
    np.random.seed(0)
    # niedrige Grundlast mit gelegentlichen Spitzen -> Prophet erzeugt reale negative untere Intervallgrenzen, obwohl Verbrauch physikalisch nie negativ sein kann
    history = _history([0.1, 0.1, 5.0, 0.1, 0.1, 0.1] * 10)
    model = _fit(history)
    target_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=6, freq="1h", tz="UTC")

    unclipped = build_prophet_forecast(model, target_index, clip_negative_forecasts=False)
    clipped = build_prophet_forecast(model, target_index, clip_negative_forecasts=True)

    # Voraussetzung für einen aussagekräftigen Test: es müssen überhaupt negative Rohwerte auftreten, sonst würde das Clipping nichts prüfen
    assert (unclipped["y_lower"] < 0).any()

    assert (clipped["y_pred"] >= 0).all()
    assert (clipped["y_lower"] >= 0).all()
    assert (clipped["y_upper"] >= 0).all()


def test_forecast_rejects_history_at_or_after_the_forecast_origin() -> None:
    history = _history([1.0, 2.0, 3.0, 4.0])
    model = _fit(history)
    # Zielzeitpunkt liegt nicht nach dem Ende der Trainingshistorie -> Kausalitätsverletzung
    overlapping_target = pd.date_range(history.index[-1], periods=1, freq="1h", tz="UTC")

    with pytest.raises(ValueError, match="at or after the forecast origin"):
        build_prophet_forecast(model, overlapping_target, clip_negative_forecasts=False)