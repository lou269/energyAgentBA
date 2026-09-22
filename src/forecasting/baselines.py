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

    history_index = pd.DatetimeIndex(history.index)
    filled_history = history.groupby(history_index.hour).ffill()

    return _reindex_at_lag(filled_history, target_index, lag_hours=24)


def build_weekly_naive_forecast(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> pd.Series:

    _validate_inputs(history, target_index)

    history_index = pd.DatetimeIndex(history.index)
    filled_history = history.groupby([history_index.dayofweek, history_index.hour]).ffill()

    return _reindex_at_lag(filled_history, target_index, lag_hours=168)


def _reindex_at_lag(
    filled_history: pd.Series,
    target_index: pd.DatetimeIndex,
    *,
    lag_hours: int,
) -> pd.Series:
    reference_index = target_index - pd.Timedelta(hours=lag_hours)
    forecast = filled_history.reindex(reference_index)

    if forecast.isna().any():
        raise ValueError(f"No observed value at the same time of day/week found within the available history ({lag_hours}h lag).")

    forecast.index = target_index.copy()
    forecast.index.name = "target_timestamp"

    return forecast.astype("float64").rename("y_pred")


def _validate_inputs(
    history: pd.Series,
    target_index: pd.DatetimeIndex,
) -> None:
    if history.index[-1] >= target_index[0]:
        raise ValueError("history may only contain timestamps before the first forecast target.")