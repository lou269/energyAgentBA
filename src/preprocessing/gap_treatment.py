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
    """Imputiert kurze Lücken kausal über alle chronologischen Splits."""

    if (
        isinstance(max_gap_intervals, bool)
        or not isinstance(max_gap_intervals, int)
        or max_gap_intervals < 1
    ):
        raise ValueError(
            "max_gap_intervals must be a positive integer."
        )

    combined_data = pd.concat(
        [
            train_data,
            validation_data,
            test_data,
        ]
    )
    combined_quality = pd.concat(
        [
            train_quality,
            validation_quality,
            test_quality,
        ]
    )

    treated, imputation_mask = _causal_impute(
        combined_data,
        combined_quality,
        max_gap_intervals=max_gap_intervals,
    )

    return (
        treated.loc[train_data.index],
        imputation_mask.loc[train_data.index],
        treated.loc[validation_data.index],
        imputation_mask.loc[validation_data.index],
        treated.loc[test_data.index],
        imputation_mask.loc[test_data.index],
    )


def _causal_impute(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    max_gap_intervals: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Füllt höchstens die konfigurierte Anzahl vergangener Intervalle."""

    treated = data.copy()
    imputation_mask = pd.DataFrame(
        False,
        index=data.index,
        columns=data.columns,
        dtype=bool,
    )

    for column in data.columns:
        coverage_mask = quality[f"{column}_coverage_mask"]
        series = treated[column].mask(~coverage_mask)

        original_missing = series.isna()
        series = series.ffill(limit=max_gap_intervals)

        imputation_mask.loc[:, column] = (
            original_missing & series.notna()
        )
        treated.loc[:, column] = series

    return treated, imputation_mask