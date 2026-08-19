from __future__ import annotations

import pandas as pd


def build_baseline_forecasts(
    history: pd.Series,
    *,
    horizon_hours: int = 24,
) -> pd.DataFrame:
    """
    Erzeugt einfache Forecast-Baselines für stündliche Verbrauchsdaten.

    Baselines:
    - Last Value: letzter bekannter Wert für alle Forecast-Schritte
    - Daily Naive: Wert derselben Stunde des Vortags
    - Weekly Seasonal Naive: Wert derselben Stunde der Vorwoche
    """
    _validate_history(
        history,
        horizon_hours=horizon_hours,
    )

    history = history.sort_index()

    cutoff = history.index[-1]

    forecast_index = pd.date_range(
        start=cutoff + pd.Timedelta(hours=1),
        periods=horizon_hours,
        freq="1h",
    )

    forecasts = pd.DataFrame(
        index=forecast_index,
    )

    forecasts["last_value"] = _last_value_forecast(
        history,
        forecast_index,
    )

    forecasts["daily_naive"] = _daily_naive_forecast(
        history,
        forecast_index,
    )

    forecasts["weekly_naive"] = _weekly_naive_forecast(
        history,
        forecast_index,
    )

    forecasts.index.name = "timestamp"

    return forecasts


def _last_value_forecast(
    history: pd.Series,
    forecast_index: pd.DatetimeIndex,
) -> pd.Series:
    """Wiederholt den letzten bekannten Verbrauchswert."""

    last_value = history.iloc[-1]

    return pd.Series(
        last_value,
        index=forecast_index,
        dtype="float64",
    )


def _daily_naive_forecast(
    history: pd.Series,
    forecast_index: pd.DatetimeIndex,
) -> pd.Series:
    """
    Verwendet für jeden Forecast-Zeitpunkt den Verbrauch
    derselben Stunde des vorherigen Tages.
    """

    reference_index = (
        forecast_index - pd.Timedelta(days=1)
    )

    values = history.reindex(reference_index)

    values.index = forecast_index

    return values.astype("float64")


def _weekly_naive_forecast(
    history: pd.Series,
    forecast_index: pd.DatetimeIndex,
) -> pd.Series:
    """
    Verwendet für jeden Forecast-Zeitpunkt den Verbrauch
    derselben Stunde der vorherigen Woche.
    """

    reference_index = (
        forecast_index - pd.Timedelta(days=7)
    )

    values = history.reindex(reference_index)

    values.index = forecast_index

    return values.astype("float64")


def _validate_history(
    history: pd.Series,
    *,
    horizon_hours: int,
) -> None:
    if not isinstance(history, pd.Series):
        raise TypeError(
            "history must be a pandas Series."
        )

    if history.empty:
        raise ValueError(
            "history must not be empty."
        )

    if not isinstance(
        history.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "history must use a DatetimeIndex."
        )

    if history.index.has_duplicates:
        raise ValueError(
            "history contains duplicate timestamps."
        )

    if horizon_hours <= 0:
        raise ValueError(
            "horizon_hours must be greater than zero."
        )

    if history.notna().sum() == 0:
        raise ValueError(
            "history contains no valid values."
        )