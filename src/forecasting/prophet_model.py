import logging

import numpy as np
import pandas as pd
from prophet import Prophet

# cmdstanpy loggt jeden Fit-Chain-Start/Stop auf INFO, das übertönt sonst jede
# eigene Log-Ausgabe während Walk-Forward-Läufen mit vielen Retrainings.
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def fit_prophet_model(
    history: pd.Series,
    *,
    growth: str,
    daily_seasonality: bool,
    weekly_seasonality: bool,
    yearly_seasonality: bool,
    country_holidays: str | None,
    local_timezone: str,
    log_transform: bool,
    interval_width: float,
    uncertainty_samples: int,
) -> Prophet:
    prophet_data = _prepare_prophet_data(history, local_timezone, log_transform)

    model = Prophet(
        growth=growth,
        daily_seasonality=daily_seasonality,  # pyright: ignore[reportArgumentType]
        weekly_seasonality=weekly_seasonality,  # pyright: ignore[reportArgumentType]
        yearly_seasonality=yearly_seasonality,  # pyright: ignore[reportArgumentType]
        interval_width=interval_width,
        uncertainty_samples=uncertainty_samples,
    )

    if country_holidays is not None:
        model.add_country_holidays(country_name=country_holidays)

    model.fit(prophet_data)

    return model


def build_prophet_forecast(
    model: Prophet,
    target_index: pd.DatetimeIndex,
    *,
    clip_negative_forecasts: bool,
    history_end: pd.Timestamp,
    local_timezone: str,
    log_transform: bool,
) -> pd.DataFrame:
    # target_index/history_end sind durch walk_forward.py strukturell garantiert
    # (UTC, stündlich, gefittetes model) - die einzige real mögliche Verletzung
    # ist ein Blick in die Zukunft.
    if history_end >= target_index[0]:
        raise ValueError("The fitted model contains history at or after the forecast origin.")

    # Lokale statt UTC-Zeit, sonst verschmiert eine Zeitumstellung im Trainingsfenster
    # die gelernte Tageskurve künstlich um eine Stunde (siehe Kap. 06/08 im Handbuch).
    future = pd.DataFrame({"ds": target_index.tz_convert(local_timezone).tz_localize(None)})

    forecast = model.predict(future)

    if log_transform:
        # Rücktransformation aus dem Log-Raum, in dem trainiert/predicted wurde.
        yhat = np.exp(forecast["yhat"].to_numpy(dtype="float64"))
        yhat_lower = np.exp(forecast["yhat_lower"].to_numpy(dtype="float64"))
        yhat_upper = np.exp(forecast["yhat_upper"].to_numpy(dtype="float64"))
    else:
        yhat = forecast["yhat"].to_numpy(dtype="float64")
        yhat_lower = forecast["yhat_lower"].to_numpy(dtype="float64")
        yhat_upper = forecast["yhat_upper"].to_numpy(dtype="float64")

    result = pd.DataFrame(
        {
            "y_pred_raw": yhat,
            "y_lower": yhat_lower,
            "y_upper": yhat_upper,
        },
        index=target_index.copy(),
    )

    if clip_negative_forecasts:
        result["y_pred"] = result["y_pred_raw"].clip(lower=0.0)
        result["y_lower"] = result["y_lower"].clip(lower=0.0)
        result["y_upper"] = result["y_upper"].clip(lower=0.0)
    else:
        result["y_pred"] = result["y_pred_raw"]

    result.index.name = "target_timestamp"

    return result[["y_pred", "y_pred_raw", "y_lower", "y_upper"]]


def _prepare_prophet_data(history: pd.Series, local_timezone: str, log_transform: bool) -> pd.DataFrame:

    valid_history = history.dropna()

    if len(valid_history) < 2:
        raise ValueError("history must contain at least two valid observations.")

    values = valid_history.to_numpy(dtype="float64")

    if log_transform:
        if (values <= 0).any():
            raise ValueError("history must be strictly positive for log_transform.")
        values = np.log(values)

    # Die explizite Konvertierung grenzt den Indextyp für Pylance ein.
    timestamps = pd.DatetimeIndex(valid_history.index)

    # Lokale statt UTC-Zeit: sonst lernt Prophet je nach Zeitumstellung im
    # Trainingsfenster zwei verschiedene reale Uhrzeiten als "dieselbe" Stunde.
    return pd.DataFrame(
        {"ds": timestamps.tz_convert(local_timezone).tz_localize(None), "y": values}
    )