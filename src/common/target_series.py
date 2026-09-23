import pandas as pd

from src.common.column_naming import imputation_column, plausibility_column, treated_column
from src.config.config_forecasting import NumericalAnalysisConfig, PreprocessingConfig
from src.config.project_config import ProjectConfig
from src.pipeline.io import read_canonical_frame, read_preprocessing_frame, read_target_meter_key
from src.preprocessing.preprocessing_runner import run_preprocessing


def read_preprocessed_target(project_config: ProjectConfig) -> tuple[pd.Series, pd.Series, pd.Series]:
    meter_key = read_target_meter_key(project_config)
    target_series = read_preprocessing_frame(project_config, "treated_hourly")[treated_column(meter_key)]
    target_imputed = read_preprocessing_frame(project_config, "imputation_mask_hourly")[imputation_column(meter_key)]
    target_value_implausible = read_preprocessing_frame(project_config, "plausibility_hourly")[plausibility_column(meter_key)]

    return target_series, target_imputed, target_value_implausible


def load_target_series(project_config: ProjectConfig) -> tuple[pd.Series, pd.Series, pd.Series, str]:
    meter_key = read_target_meter_key(project_config)
    target_column = treated_column(meter_key)
    mask_column = imputation_column(meter_key)
    plausibility_col = plausibility_column(meter_key)

    preprocessing_result = run_preprocessing(
        read_canonical_frame(project_config, "canonical_data_15min"),
        read_canonical_frame(project_config, "canonical_quality_15min"),
        read_canonical_frame(project_config, "canonical_data_hourly"),
        read_canonical_frame(project_config, "canonical_quality_hourly"),
        PreprocessingConfig(),
        project_config.timezone,
        sample_period_hours_15min=NumericalAnalysisConfig().sample_period_hours_15min,
        sample_period_hours_hourly=NumericalAnalysisConfig().sample_period_hours_hourly,
    )

    target_series = preprocessing_result.treated_hourly[target_column]
    target_imputed = preprocessing_result.imputation_mask_hourly[mask_column]
    target_value_implausible = preprocessing_result.plausibility_hourly[plausibility_col]

    return target_series, target_imputed, target_value_implausible, meter_key