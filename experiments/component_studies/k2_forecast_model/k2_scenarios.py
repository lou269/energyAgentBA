import pandas as pd


def slice_comparison_window(
    target_series: pd.Series,
    target_imputed: pd.Series,
    *,
    split_start: pd.Timestamp,
    split_end: pd.Timestamp,
    mode: str,
    coldstart_hours: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    # rolling startet wie daily_cycle mit coldstart_hours Historie, macro mit allem vor dem Split (70/15/15)
    history_start = split_start - pd.Timedelta(hours=coldstart_hours) if mode == "rolling" else None
    history = target_series.loc[history_start:split_start - pd.Timedelta(hours=1)]

    return history, target_series.loc[split_start:split_end], target_imputed.loc[split_start:split_end]
