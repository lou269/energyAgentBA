from __future__ import annotations

import pandas as pd


def build_last_value_forecast(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> pd.Series:
    """Wiederholt den letzten beobachteten Wert für alle Zielzeitpunkte."""

    _validate_inputs(history, target_index)

    observed_history = history.dropna()

    if observed_history.empty:
        raise ValueError("history contains no observed values.")

    forecast = pd.Series(
        float(observed_history.iloc[-1]),
        index=target_index.copy(),
        dtype="float64",
        name="y_pred",
    )
    forecast.index.name = "target_timestamp"

    return forecast


def build_daily_naive_forecast(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> pd.Series:
    _validate_inputs(history, target_index)

    reference_index = target_index - pd.Timedelta(hours=24)
    forecast = history.reindex(reference_index)

    if forecast.isna().any():
        raise ValueError("Daily naive forecast requires an observed or causally imputed value 24 hours before every target timestamp.")

    forecast.index = target_index.copy()
    forecast.index.name = "target_timestamp"

    return forecast.astype("float64").rename("y_pred")


def build_weekly_naive_forecast(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> pd.Series:
    """Verwendet den Wert genau 168 Stunden vor jedem Zielzeitpunkt."""

    _validate_inputs(history, target_index)

    reference_index = target_index - pd.Timedelta(hours=168)
    forecast = history.reindex(reference_index)

    if forecast.isna().any():
        raise ValueError("Weekly naive forecast requires an observed or causally imputed value 168 hours before every target timestamp.")

    forecast.index = target_index.copy()
    forecast.index.name = "target_timestamp"

    return forecast.astype("float64").rename("y_pred")


def _validate_inputs(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> None:
    if not isinstance(history, pd.Series):
        raise TypeError("history must be a pandas Series.")

    if history.empty:
        raise ValueError("history must not be empty.")

    if not isinstance(history.index, pd.DatetimeIndex):
        raise TypeError("history must use a DatetimeIndex.")

    if not isinstance(target_index, pd.DatetimeIndex):
        raise TypeError("target_index must be a DatetimeIndex.")

    if target_index.empty:
        raise ValueError("target_index must not be empty.")

    if history.index.has_duplicates:
        raise ValueError("history contains duplicate timestamps.")

    if target_index.has_duplicates:
        raise ValueError("target_index contains duplicate timestamps.")

    if not history.index.is_monotonic_increasing:
        raise ValueError("history must be sorted chronologically.")

    if str(history.index.tz) != "UTC" or str(target_index.tz) != "UTC":
        raise ValueError("history and target_index must use UTC.")

    expected_target_index = pd.date_range(
        start=target_index[0],
        periods=len(target_index),
        freq="1h",
    )

    if not target_index.equals(expected_target_index):
        raise ValueError("target_index must contain consecutive hourly timestamps.")

    if history.index[-1] >= target_index[0]:
        raise ValueError("history may only contain timestamps before the first forecast target.")