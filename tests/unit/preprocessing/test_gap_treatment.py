# python -m pytest tests/unit/preprocessing/test_gap_treatment.py -v

import pandas as pd

from src.common.column_naming import imputation_column, treated_column
from src.preprocessing.gap_treatment import apply_gap_treatment

TREATED = treated_column("m1")
IMPUTED = imputation_column("m1")


def _frame(
    index: pd.DatetimeIndex, values: list[float | None], column: str = "m1"
) -> pd.DataFrame:
    return pd.DataFrame({column: values}, index=index)


def _quality(
    index: pd.DatetimeIndex, coverage: list[bool], column: str = "m1"
) -> pd.DataFrame:
    return pd.DataFrame({f"{column}_coverage_mask": coverage}, index=index)


def test_short_gap_is_filled_long_gap_stays_empty() -> None:
    index = pd.date_range("2020-01-01", periods=8, freq="1h")
    values = [10.0, None, 12.0, None, None, None, 16.0, 17.0]
    data = _frame(index, values)
    quality = _quality(index, [value is not None for value in values])

    treated, imputation_mask = apply_gap_treatment(
        data, quality, max_gap_intervals=2, resolution="hourly", method="ffill"
    )

    assert treated[TREATED].isna().tolist() == [
        False,
        False,
        False,
        True,
        True,
        True,
        False,
        False,
    ]
    assert treated[TREATED].dropna().tolist() == [10.0, 10.0, 12.0, 16.0, 17.0]
    assert imputation_mask[IMPUTED].tolist() == [
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
    ]


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
