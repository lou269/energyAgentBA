from dataclasses import dataclass
from typing import Literal

ProductionGapMethod = Literal["ffill", "none"]


@dataclass(frozen=True)
class PreprocessingConfig:
    train_share: float = 0.70
    validation_share: float = 0.15

    gap_treatment_method: ProductionGapMethod = "ffill"
    max_imputation_gap_15min: int = 4
    max_imputation_gap_hourly: int = 2 # bleibt 2h -> nicht das gleiche wie max_availibility_gap_hours

    stuck_value_min_hours: float = 6.0

    lags_15min: tuple[int, ...] = (1, 4, 96, 672)
    lags_hourly: tuple[int, ...] = (1, 24, 168)

    rolling_windows_15min: tuple[int, ...] = (4, 96, 672)
    rolling_windows_hourly: tuple[int, ...] = (24, 168)
    
    feature_variance_threshold: float = 0.0