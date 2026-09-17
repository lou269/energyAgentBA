import pandas as pd

from src.common.column_naming import imputation_column, treated_column
from src.common.timestamps import local_day_index


def exclude_incomplete_days(
    treated: pd.DataFrame,
    imputation_mask: pd.DataFrame,
    *,
    local_timezone: str,
    sample_period_hours: float,
    max_single_gap_hours: float,
    max_daily_missing_share: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    treated = treated.copy()
    imputation_mask = imputation_mask.copy()

    treated_suffix = treated_column("")
    day_key = local_day_index(treated.index, local_timezone)

    for column in treated.columns:
        meter_key = column.removesuffix(treated_suffix)
        imputation_col = imputation_column(meter_key)

        series = treated[column]
        missing = series.isna()

        gap_ids = missing.ne(missing.shift(fill_value=False)).cumsum()
        gap_length_hours = missing.groupby(gap_ids).transform("sum") * sample_period_hours

        worst_gap_per_day = gap_length_hours.where(missing).groupby(day_key).max()
        missing_share_per_day = missing.groupby(day_key).mean()

        excluded_days = worst_gap_per_day.index[
            worst_gap_per_day.gt(max_single_gap_hours) | missing_share_per_day.gt(max_daily_missing_share)
        ]

        excluded_rows = day_key.isin(excluded_days)

        treated.loc[excluded_rows, column] = float("nan")
        imputation_mask.loc[excluded_rows, imputation_col] = False

    return treated, imputation_mask

