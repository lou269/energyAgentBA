import pandas as pd

from src.common.timestamps import shift_local_days


def slice_comparison_window(
    target_series: pd.Series,
    target_imputed: pd.Series,
    *,
    split_start: pd.Timestamp,
    split_end: pd.Timestamp,
    mode: str,
    coldstart_days: int,
    local_timezone: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    # rolling startet wie daily_cycle mit coldstart_days Historie, macro mit allem vor dem Split (70/15/15)
    history_start = shift_local_days(split_start, -coldstart_days, local_timezone) if mode == "rolling" else None
    history = target_series.loc[history_start:split_start - pd.Timedelta(hours=1)]

    return history, target_series.loc[split_start:split_end], target_imputed.loc[split_start:split_end]