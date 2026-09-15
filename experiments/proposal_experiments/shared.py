from collections.abc import Sequence

import pandas as pd

from src.common.column_naming import imputation_column, treated_column
from src.config.config_forecasting import PreprocessingConfig
from src.config.project_config import ProjectConfig
from src.pipeline.io import read_canonical_frame, read_target_meter_key
from src.preprocessing.preprocessing_runner import run_preprocessing


def load_target_series(project_config: ProjectConfig) -> tuple[pd.Series, pd.Series, str]:
    """Lädt die kanonische Mains-Zielreihe auf Stundenbasis nach Gap-Treatment, plus Imputation-Maske und meter_key"""
    meter_key = read_target_meter_key(project_config)
    target_column = treated_column(meter_key)
    mask_column = imputation_column(meter_key)

    preprocessing_result = run_preprocessing(
        read_canonical_frame(project_config, "canonical_data_15min"),
        read_canonical_frame(project_config, "canonical_quality_15min"),
        read_canonical_frame(project_config, "canonical_data_hourly"),
        read_canonical_frame(project_config, "canonical_quality_hourly"),
        PreprocessingConfig()
    )

    target_series = preprocessing_result.treated_hourly[target_column]
    target_imputed = preprocessing_result.imputation_mask_hourly[mask_column]

    return target_series, target_imputed, meter_key



def build_decision_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    margin_before_days: int,
    margin_after_days: int,
) -> tuple[pd.Timestamp, ...]:
    start = window_start - pd.Timedelta(days=margin_before_days)
    end = window_end + pd.Timedelta(days=margin_after_days)

    return tuple(pd.date_range(start, end, freq="24h", tz="UTC"))


def subtract_channels_in_window(
    mains: pd.Series,
    appliance_data_hourly: pd.DataFrame,
    meter_keys: Sequence[str],
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> pd.Series:
    if not meter_keys:
        raise ValueError("meter_keys must not be empty.")

    missing = set(meter_keys) - set(appliance_data_hourly.columns)
    if missing:
        raise ValueError(f"appliance_data_hourly is missing columns: {', '.join(sorted(missing))}")

    window_mask = (mains.index >= window_start) & (mains.index < window_end)
    window_index = mains.index[window_mask]

    combined_load = (
        appliance_data_hourly.loc[:, meter_keys]
        .reindex(window_index)
        .fillna(0.0)
        .sum(axis=1)
    )

    adjusted = mains.copy()
    adjusted.loc[window_index] = (adjusted.loc[window_index] - combined_load).clip(lower=0.0)

    return adjusted