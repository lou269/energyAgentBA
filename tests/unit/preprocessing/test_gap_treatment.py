# python -m pytest tests/unit/preprocessing/test_gap_treatment.py -v

import pandas as pd
import pytest

from src.common.column_naming import imputation_column, treated_column
from src.preprocessing.gap_treatment import apply_gap_treatment, build_gap_treated_data

TREATED = treated_column("m1")
IMPUTED = imputation_column("m1")


def _frame(index: pd.DatetimeIndex, values: list[float | None], column: str = "m1") -> pd.DataFrame:
    return pd.DataFrame({column: values}, index=index)


def _quality(index: pd.DatetimeIndex, coverage: list[bool], column: str = "m1") -> pd.DataFrame:
    return pd.DataFrame({f"{column}_coverage_mask": coverage}, index=index)


def test_short_gap_is_filled_long_gap_stays_empty() -> None:
    index = pd.date_range("2020-01-01", periods=8, freq="1h")
    values = [10.0, None, 12.0, None, None, None, 16.0, 17.0]
    data = _frame(index, values)
    quality = _quality(index, [value is not None for value in values])

    treated, imputation_mask = apply_gap_treatment(
        data, quality, max_gap_intervals=2, resolution="hourly", method="ffill"
    )

    assert treated[TREATED].isna().tolist() == [False, False, False, True, True, True, False, False]
    assert treated[TREATED].dropna().tolist() == [10.0, 10.0, 12.0, 16.0, 17.0]
    assert imputation_mask[IMPUTED].tolist() == [False, True, False, False, False, False, False, False]


def test_low_quality_value_is_treated_as_missing_and_filled() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="1h")
    data = _frame(index, [10.0, 99.0, 12.0])
    quality = _quality(index, [True, False, True])

    treated, imputation_mask = apply_gap_treatment(
        data, quality, max_gap_intervals=2, resolution="hourly", method="ffill"
    )

    assert treated[TREATED].tolist() == [10.0, 10.0, 12.0]
    assert imputation_mask[IMPUTED].tolist() == [False, True, False]


def test_method_none_never_fills() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="1h")
    values = [10.0, None, 12.0]
    data = _frame(index, values)
    quality = _quality(index, [value is not None for value in values])

    treated, imputation_mask = apply_gap_treatment(
        data, quality, max_gap_intervals=2, resolution="hourly", method="none"
    )

    assert treated[TREATED].isna().tolist() == [False, True, False]
    assert not imputation_mask[IMPUTED].any()


def test_build_gap_treated_data_fills_across_split_boundary() -> None:
    train_index = pd.date_range("2020-01-01T00:00:00", periods=3, freq="1h")
    validation_index = pd.date_range("2020-01-01T03:00:00", periods=2, freq="1h")
    test_index = pd.date_range("2020-01-01T05:00:00", periods=2, freq="1h")

    train_data = _frame(train_index, [10.0, 11.0, 12.0])
    validation_data = _frame(validation_index, [None, 14.0])
    test_data = _frame(test_index, [20.0, 21.0])

    train_quality = _quality(train_index, [True, True, True])
    validation_quality = _quality(validation_index, [False, True])
    test_quality = _quality(test_index, [True, True])

    (
        train_treated,
        train_mask,
        validation_treated,
        validation_mask,
        test_treated,
        test_mask,
    ) = build_gap_treated_data(
        train_data,
        train_quality,
        validation_data,
        validation_quality,
        test_data,
        test_quality,
        max_gap_intervals=2,
        resolution="hourly",
        method="ffill",
    )

    # Lücke am Anfang von validation wird aus dem letzten Trainwert gefüllt, nur möglich weil build_gap_treated_data über alle Splits hinweg konkateniert.
    assert validation_treated[TREATED].tolist() == [12.0, 14.0]
    assert validation_mask[IMPUTED].tolist() == [True, False]
    assert train_treated.index.equals(train_index)
    assert test_treated[TREATED].tolist() == [20.0, 21.0]


def test_build_gap_treated_data_rejects_global_linear_interpolation() -> None:
    index = pd.date_range("2020-01-01", periods=2, freq="1h")
    data = _frame(index, [10.0, 11.0])
    quality = _quality(index, [True, True])

    with pytest.raises(ValueError, match="Linear interpolation"):
        build_gap_treated_data(
            data, quality, data, quality, data, quality,
            max_gap_intervals=2,
            resolution="hourly",
            method="linear",
        )
