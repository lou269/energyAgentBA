import pandas as pd

from src.common.column_naming import (
    meter_key_from_data_column,
    plausibility_column,
    quality_column,
)


def build_plausibility_flags(
    data: pd.DataFrame,
    quality: pd.DataFrame,
    *,
    stuck_value_min_hours: float,
    sample_period_hours: float,
    resolution: str,
) -> pd.DataFrame:
    meter_keys = [
        meter_key_from_data_column(column, resolution) for column in data.columns
    ]

    flags = pd.DataFrame(
        False,
        index=data.index,
        columns=[plausibility_column(key) for key in meter_keys],
        dtype=bool,
    )

    for column, meter_key in zip(data.columns, meter_keys):
        coverage_column = quality_column(meter_key, "coverage_mask")
        coverage_mask = quality[coverage_column].fillna(False).astype(bool)

        flags.loc[:, plausibility_column(meter_key)] = flag_implausible_values(
            data[column].where(coverage_mask),
            stuck_value_min_hours=stuck_value_min_hours,
            sample_period_hours=sample_period_hours,
        )

    return flags


# NaN unterbricht einen Streak, nicht gemessene oder aufgefüllte Stunden deshalb vorher auf NaN setzen
def flag_implausible_values(
    series: pd.Series,
    *,
    stuck_value_min_hours: float,
    sample_period_hours: float,
) -> pd.Series:
    unchanged = series.eq(series.shift(1)) & series.notna()

    stuck_periods = unchanged.groupby((~unchanged).cumsum()).cumsum()
    stuck_streak_hours = stuck_periods * sample_period_hours

    return (series < 0) | (stuck_streak_hours >= stuck_value_min_hours)
