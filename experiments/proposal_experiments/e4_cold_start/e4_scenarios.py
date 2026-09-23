import pandas as pd

from src.common.timestamps import local_midnight_utc


def slice_coldstart_window(
    target_series: pd.Series,
    target_imputed: pd.Series,
    *,
    start_date: str,
    coldstart_days: int,
    evaluation_days: int,
    local_timezone: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    start = local_midnight_utc(start_date, local_timezone)
    history_start = local_midnight_utc(start_date, local_timezone, days_offset=-coldstart_days)
    evaluation_end = local_midnight_utc(start_date, local_timezone, days_offset=evaluation_days) - pd.Timedelta(hours=1)

    history = target_series.loc[history_start:start - pd.Timedelta(hours=1)]
    targets = target_series.loc[start:evaluation_end]

    return history, targets, target_imputed.loc[start:evaluation_end]