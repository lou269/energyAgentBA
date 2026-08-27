from __future__ import annotations

import pandas as pd


def build_gap_treated_data(
    train_data: pd.DataFrame,
    train_quality: pd.DataFrame,
    validation_data: pd.DataFrame,
    validation_quality: pd.DataFrame,
    test_data: pd.DataFrame,
    test_quality: pd.DataFrame,
    max_gap_intervals: int,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Imputiert kurze Gaps kausal über chronologische Splits."""

    if max_gap_intervals < 1:
        raise ValueError("max_gap_intervals must be at least 1.")

    train_data, train_mask, last_values = _causal_impute(
        train_data,
        train_quality,
        max_gap_intervals=max_gap_intervals,
    )

    validation_data, validation_mask, last_values = _causal_impute(
        validation_data,
        validation_quality,
        max_gap_intervals=max_gap_intervals,
        initial_values=last_values,
    )

    test_data, test_mask, _ = _causal_impute(
        test_data,
        test_quality,
        max_gap_intervals=max_gap_intervals,
        initial_values=last_values,
    )

    return (
        train_data,
        train_mask,
        validation_data,
        validation_mask,
        test_data,
        test_mask,
    )


def _causal_impute(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    max_gap_intervals: int,
    initial_values: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Füllt höchstens die konfigurierte Anzahl vergangener Intervalle."""

    treated = data.copy()
    imputation_mask = pd.DataFrame(
        False,
        index=data.index,
        columns=data.columns,
        dtype=bool,
    )

    if data.empty:
        if initial_values is None:
            last_values = pd.Series(index=data.columns, dtype=float)
        else:
            last_values = initial_values.reindex(data.columns).copy()

        return treated, imputation_mask, last_values

    for column in data.columns:
        coverage_mask = quality[f"{column}_coverage_mask"]
        series = treated[column].mask(~coverage_mask)

        if initial_values is not None:
            previous = pd.Series(
                [initial_values[column]],
                index=[series.index[0] - pd.Timedelta(nanoseconds=1)],
            )
            series = pd.concat([previous, series])

        original_missing = series.isna()
        series = series.ffill(limit=max_gap_intervals)

        if initial_values is not None:
            series = series.iloc[1:]
            original_missing = original_missing.iloc[1:]

        imputation_mask.loc[:, column] = (
            original_missing & series.notna()
        )
        treated.loc[:, column] = series

    # Kein erneutes unbegrenztes ffill: Eine lange terminale Lücke
    # bleibt fehlend und kann keinen veralteten Zustand weitergeben.
    last_values = treated.iloc[-1].copy()

    return treated, imputation_mask, last_values