import pandas as pd


def build_plausibility_flags(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    stuck_value_min_hours: float,
    sample_period_hours: float,
) -> pd.DataFrame:
    flags = pd.DataFrame(
        False,
        index=data.index,
        columns=data.columns,
        dtype=bool,
    )

    for column in data.columns:
        coverage_column = f"{column}_coverage_mask"
        coverage_mask = quality[coverage_column].fillna(False).astype(bool)
     

        series = data[column].where(coverage_mask)

        unchanged = series.eq(series.shift(1)) & series.notna()

        stuck_periods = unchanged.groupby((~unchanged).cumsum()).cumsum()
        stuck_streak_hours = stuck_periods * sample_period_hours

        flags.loc[:, column] = (series < 0) | (stuck_streak_hours >= stuck_value_min_hours)

    return flags