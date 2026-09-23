import pandas as pd

from src.common.timestamps import reindex_at_local_lag


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
    local_timezone: str,
) -> pd.Series:

    _validate_inputs(history, target_index)

    local_index = pd.DatetimeIndex(history.index).tz_convert(local_timezone)
    filled_history = history.groupby(local_index.hour).ffill()

    return _reindex_at_lag(filled_history, target_index, lag_days=1, local_timezone=local_timezone)


def build_weekly_naive_forecast(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
    local_timezone: str,
) -> pd.Series:

    _validate_inputs(history, target_index)

    local_index = pd.DatetimeIndex(history.index).tz_convert(local_timezone)
    filled_history = history.groupby([local_index.dayofweek, local_index.hour]).ffill()

    return _reindex_at_lag(filled_history, target_index, lag_days=7, local_timezone=local_timezone)


def _reindex_at_lag(
    filled_history: pd.Series,
    target_index: pd.DatetimeIndex,
    *,
    lag_days: int,
    local_timezone: str,
) -> pd.Series:
    forecast = reindex_at_local_lag(filled_history, target_index, lag_days, local_timezone)

    if forecast.isna().any():
        raise ValueError(f"No observed value at the same local time of day/week found within the available history ({lag_days}-day lag).")

    forecast.index.name = "target_timestamp"

    return forecast.astype("float64").rename("y_pred")


def _validate_inputs(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> None:
    if history.index[-1] >= target_index[0]:
        raise ValueError("history may only contain timestamps before the first forecast target.")