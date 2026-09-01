from __future__ import annotations

import numpy as np
import pandas as pd
from prophet import Prophet


def fit_prophet_model(
    history: pd.Series,
    *,
    growth: str,
    daily_seasonality: bool,
    weekly_seasonality: bool,
    yearly_seasonality: bool,
    interval_width: float,
) -> Prophet:
    """Fittet Prophet auf der für den Forecast erlaubten History."""

    prophet_data = _prepare_prophet_data(history)

    # Prophet unterstützt bool, obwohl die bereitgestellten Typinformationen
    # für die Seasonality-Parameter nur str ausweisen.
    model = Prophet(
        growth=growth,
        daily_seasonality=daily_seasonality,  # pyright: ignore[reportArgumentType]
        weekly_seasonality=weekly_seasonality,  # pyright: ignore[reportArgumentType]
        yearly_seasonality=yearly_seasonality,  # pyright: ignore[reportArgumentType]
        interval_width=interval_width,
    )
    model.fit(prophet_data)

    return model


def build_prophet_forecast(
    model: Prophet,
    target_index: pd.DatetimeIndex,
    *,
    clip_negative_forecasts: bool,
) -> pd.DataFrame:
    """
    Erstellt Prognosen für die explizit übergebenen Zielzeitpunkte.

    Rohprognosen und Vorhersageintervalle bleiben unverändert erhalten.
    Optionales Clipping betrifft ausschließlich y_pred.
    """

    _validate_utc_index(target_index, name="target_index")

    if model.history is None or model.history.empty:
        raise ValueError("model must be fitted before forecasting.")

    history_end = pd.Timestamp(
        model.history["ds"].max()
    ).tz_localize("UTC")

    if history_end >= target_index[0]:
        raise ValueError(
            "The fitted model contains history at or after the "
            "forecast origin."
        )

    # Prophet verarbeitet keine timezone-aware Zeitstempel.
    future = pd.DataFrame(
        {
            "ds": (
                target_index
                .tz_convert("UTC")
                .tz_localize(None)
            )
        }
    )

    forecast = model.predict(future)

    result = pd.DataFrame(
        {
            "y_pred_raw": forecast["yhat"].to_numpy(dtype="float64"),
            "y_lower": forecast["yhat_lower"].to_numpy(dtype="float64"),
            "y_upper": forecast["yhat_upper"].to_numpy(dtype="float64"),
        },
        index=target_index.copy(),
    )

    if clip_negative_forecasts:
        result["y_pred"] = result["y_pred_raw"].clip(lower=0.0)
    else:
        result["y_pred"] = result["y_pred_raw"]

    result.index.name = "target_timestamp"

    return result[
        [
            "y_pred",
            "y_pred_raw",
            "y_lower",
            "y_upper",
        ]
    ]


def _prepare_prophet_data(history: pd.Series) -> pd.DataFrame:
    """Überführt eine UTC-Zeitreihe in Prophets ds-y-Schema."""

    if not isinstance(history, pd.Series):
        raise TypeError("history must be a pandas Series.")

    _validate_utc_index(history.index, name="history.index")

    valid_history = history.dropna()

    if len(valid_history) < 2:
        raise ValueError(
            "history must contain at least two valid observations."
        )

    try:
        values = valid_history.to_numpy(dtype="float64")
    except (TypeError, ValueError) as error:
        raise TypeError(
            "history must contain numeric values."
        ) from error

    if not np.isfinite(values).all():
        raise ValueError("history contains infinite values.")

    # Die explizite Konvertierung grenzt den Indextyp für Pylance ein.
    timestamps = pd.DatetimeIndex(valid_history.index)

    return pd.DataFrame(
        {
            "ds": timestamps.tz_convert("UTC").tz_localize(None),
            "y": values,
        }
    )


def _validate_utc_index(
    index: pd.Index,
    *,
    name: str,
) -> None:
    """Prüft die gemeinsamen Zeitindex-Garantien des Moduls."""

    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(f"{name} must be a DatetimeIndex.")

    if index.empty:
        raise ValueError(f"{name} must not be empty.")

    if index.has_duplicates:
        raise ValueError(f"{name} contains duplicate timestamps.")

    if not index.is_monotonic_increasing:
        raise ValueError(f"{name} must be sorted chronologically.")

    if str(index.tz) != "UTC":
        raise ValueError(f"{name} must use UTC.")