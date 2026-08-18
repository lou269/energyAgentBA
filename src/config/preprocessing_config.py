from dataclasses import dataclass


@dataclass(frozen=True)
class PreprocessingConfig:
    min_aggregation_coverage_share: float = 0.80

    train_share: float = 0.70
    validation_share: float = 0.15

    max_imputation_gap_15min: int = 4
    max_imputation_gap_hourly: int = 2

    lags_15min: tuple[int, ...] = (1, 4, 96, 672)
    lags_hourly: tuple[int, ...] = (1, 24, 168)

    rolling_windows_15min: tuple[int, ...] = (4, 96, 672)
    rolling_windows_hourly: tuple[int, ...] = (24, 168)
    
    feature_variance_threshold: float = 0.0