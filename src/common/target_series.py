import pandas as pd

from src.common.column_naming import (
    imputation_column,
    plausibility_column,
    treated_column,
)
from src.config.project_config import ProjectConfig
from src.pipeline.io import (
    read_preprocessing_frame,
    read_split_row,
    read_target_meter_key,
)


def read_preprocessed_target(
    project_config: ProjectConfig, split: str
) -> tuple[pd.Series, pd.Series, pd.Series]:
    meter_key = read_target_meter_key(project_config)
    window = read_split_row(project_config, split)["window"]
    target_series = read_preprocessing_frame(project_config, "treated_hourly", window)[
        treated_column(meter_key)
    ]
    target_imputed = read_preprocessing_frame(
        project_config, "imputation_mask_hourly", window
    )[imputation_column(meter_key)]
    target_value_implausible = read_preprocessing_frame(
        project_config, "plausibility_hourly", window
    )[plausibility_column(meter_key)]

    return target_series, target_imputed, target_value_implausible


def read_preprocessed_daily_target(
    project_config: ProjectConfig, split: str
) -> pd.Series:
    meter_key = read_target_meter_key(project_config)

    window = read_split_row(project_config, split)["window"]

    return read_preprocessing_frame(project_config, "treated_daily", window)[
        treated_column(meter_key)
    ]
