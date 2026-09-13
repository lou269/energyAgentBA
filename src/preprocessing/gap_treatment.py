from typing import Literal

import pandas as pd

from src.common.column_naming import imputation_column, meter_key_from_data_column, quality_column, treated_column
from src.common.gap_masking import short_gap_mask

GapTreatmentMethod = Literal["ffill", "linear", "none"]


def build_gap_treated_data(
    train_data: pd.DataFrame,
    train_quality: pd.DataFrame,
    validation_data: pd.DataFrame,
    validation_quality: pd.DataFrame,
    test_data: pd.DataFrame,
    test_quality: pd.DataFrame,
    max_gap_intervals: int,
    resolution: str,
    method: GapTreatmentMethod = "ffill",
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:

    if method == "linear":
        raise ValueError("Linear interpolation must not be applied globally across all splits. Use apply_gap_treatment() only on history available before the relevant forecast cutoff.")

    combined_data = pd.concat([train_data, validation_data, test_data])

    combined_quality = pd.concat([train_quality, validation_quality, test_quality])

    treated, imputation_mask = apply_gap_treatment(
        combined_data,
        combined_quality,
        max_gap_intervals=max_gap_intervals,
        resolution=resolution,
        method=method,
    )

    return (
        treated.loc[train_data.index],
        imputation_mask.loc[train_data.index],
        treated.loc[validation_data.index],
        imputation_mask.loc[validation_data.index],
        treated.loc[test_data.index],
        imputation_mask.loc[test_data.index],
    )


def apply_gap_treatment(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    max_gap_intervals: int,
    resolution: str,
    method: GapTreatmentMethod,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _validate_inputs(data, quality, max_gap_intervals=max_gap_intervals, method=method)

    meter_keys = [meter_key_from_data_column(column, resolution) for column in data.columns]

    treated = pd.DataFrame(
        index=data.index,
        columns=[treated_column(key) for key in meter_keys],
        dtype=float,
    )
    imputation_mask = pd.DataFrame(
        False,
        index=data.index,
        columns=[imputation_column(key) for key in meter_keys],
        dtype=bool,
    )

    for column, meter_key in zip(data.columns, meter_keys):
        coverage_column = quality_column(meter_key, "coverage_mask")
        coverage_mask = (
            quality[coverage_column]
            .fillna(False)
            .astype(bool)
        )

        series = data[column].where(coverage_mask)
        missing = series.isna()
        short_gap = short_gap_mask(missing, max_gap_intervals)

        if method == "ffill":
            candidate = series.ffill()
        elif method == "linear":
            candidate = series.interpolate(method="time", limit_area="inside")
        else:
            candidate = series.copy()

        # Ausschließlich vollständige Lücken innerhalb des Limits ersetzen.
        # Dadurch wird kein Anfang einer zu langen Lücke aufgefüllt.
        filled = series.where(~short_gap, candidate)

        treated.loc[:, treated_column(meter_key)] = filled
        imputation_mask.loc[:, imputation_column(meter_key)] = missing & filled.notna()

    return treated, imputation_mask


def _validate_inputs(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    max_gap_intervals: int,
    method: GapTreatmentMethod,
) -> None:
    if (
        isinstance(max_gap_intervals, bool)
        or not isinstance(max_gap_intervals, int)
        or max_gap_intervals < 1
    ):
        raise ValueError("max_gap_intervals must be a positive integer.")

    if method not in {"ffill", "linear", "none"}:
        raise ValueError(f"Unsupported gap treatment method: {method}.")

    if data.empty:
        raise ValueError("data must not be empty.")

    if not data.index.equals(quality.index):
        raise ValueError("data and quality must use the same index.")

    if data.index.has_duplicates:
        raise ValueError("data must not contain duplicate timestamps.")

    if not data.index.is_monotonic_increasing:
        raise ValueError("data must be sorted chronologically.")

    if method == "linear" and not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError("Linear interpolation requires a DatetimeIndex.")