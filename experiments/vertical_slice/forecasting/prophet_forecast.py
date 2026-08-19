from __future__ import annotations

import pandas as pd
from prophet import Prophet
from prophet.plot import plot_plotly


def build_prophet_forecasts(
    history: pd.Series,
    *,
    horizon_hours: int = 24,
    rolling_window_days: int = 7,
) -> dict[str, pd.DataFrame]:
    """
    Erzeugt zwei Prophet-Forecasts:

    1. full_history:
       Prophet wird auf der gesamten bis zum Cutoff bekannten
       Historie trainiert.

    2. rolling_7d:
       Prophet wird nur auf den letzten 7 Tagen vor dem Cutoff
       trainiert.

    Beide Varianten prognostizieren die nächsten 24 Stunden.
    """
    _validate_history(
        history,
        horizon_hours=horizon_hours,
        rolling_window_days=rolling_window_days,
    )

    history = history.sort_index()

    rolling_hours = rolling_window_days * 24

    rolling_history = history.tail(
        rolling_hours
    )

    full_history_forecast = _fit_prophet(
        history,
        horizon_hours=horizon_hours,
    )

    rolling_forecast = _fit_prophet(
        rolling_history,
        horizon_hours=horizon_hours,
    )

    return {
        "full_history": full_history_forecast,
        "rolling_7d": rolling_forecast,
    }


def _fit_prophet(
    history: pd.Series,
    *,
    horizon_hours: int,
) -> pd.DataFrame:
    """
    Trainiert Prophet auf einer gegebenen Historie
    und erzeugt einen stündlichen Forecast.
    """
    prophet_data = _prepare_prophet_data(
        history
    )

    model = Prophet(
        daily_seasonality=True,  # pyright: ignore[reportArgumentType]
        weekly_seasonality=True,  # pyright: ignore[reportArgumentType]
        yearly_seasonality=False,  # pyright: ignore[reportArgumentType]
    )

    model.fit(prophet_data)

    future = model.make_future_dataframe(
        periods=horizon_hours,
        freq="h",
        include_history=False,
    )

    forecast = model.predict(future)

    forecast = model.predict(future)
    '''
    fig = plot_plotly(
        model,
        forecast,
    )

    fig.show()
    '''
    result = forecast[
        [
            "ds",
            "yhat",
            "yhat_lower",
            "yhat_upper",
        ]
    ].copy()
    result = forecast[
        [
            "ds",
            "yhat",
            "yhat_lower",
            "yhat_upper",
        ]
    ].copy()

    result = result.rename(
        columns={
            "ds": "timestamp",
        }
    )

    # Die Eingangsdaten sind UTC.
    # Prophet arbeitet intern mit timezone-naiven Timestamps.
    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        utc=True,
    )

    result = result.set_index(
        "timestamp"
    )

    return result


def _prepare_prophet_data(
    history: pd.Series,
) -> pd.DataFrame:
    """
    Wandelt die stündliche Series in das von Prophet
    erwartete Schema mit ds und y um.
    """
    valid_history = history.dropna()

    timestamps = pd.DatetimeIndex(
        valid_history.index
    )

    if timestamps.tz is not None:
        timestamps = (
            timestamps
            .tz_convert("UTC")
            .tz_localize(None)
        )

    return pd.DataFrame(
        {
            "ds": timestamps,
            "y": valid_history.to_numpy(),
        }
    )


def _validate_history(
    history: pd.Series,
    *,
    horizon_hours: int,
    rolling_window_days: int,
) -> None:
    if not isinstance(
        history,
        pd.Series,
    ):
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

    if rolling_window_days <= 0:
        raise ValueError(
            "rolling_window_days must be greater than zero."
        )

    if history.notna().sum() == 0:
        raise ValueError(
            "history contains no valid values."
        )

    required_rolling_hours = (
        rolling_window_days * 24
    )

    if history.notna().sum() < required_rolling_hours:
        raise ValueError(
            "history does not contain enough values "
            f"for a {rolling_window_days}-day rolling window."
        )