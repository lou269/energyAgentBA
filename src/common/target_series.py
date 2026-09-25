import pandas as pd

from src.common.column_naming import (
    imputation_column,
    plausibility_column,
    treated_column,
)
from src.config.project_config import ProjectConfig
from src.pipeline.io import read_preprocessing_frame, read_target_meter_key


def read_preprocessed_target(
    project_config: ProjectConfig,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    meter_key = read_target_meter_key(project_config)
    target_series = read_preprocessing_frame(project_config, "treated_hourly")[
        treated_column(meter_key)
    ]
    target_imputed = read_preprocessing_frame(project_config, "imputation_mask_hourly")[
        imputation_column(meter_key)
    ]
    target_value_implausible = read_preprocessing_frame(
        project_config, "plausibility_hourly"
    )[plausibility_column(meter_key)]

    return target_series, target_imputed, target_value_implausible
