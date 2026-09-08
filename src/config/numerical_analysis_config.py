from dataclasses import dataclass


@dataclass(frozen=True)
class NumericalAnalysisConfig:
    sample_period_hours_15min: float = 0.25
    sample_period_hours_hourly: float = 1.0

    short_term_window_15min: int = 96
    short_term_window_hourly: int = 24

    long_term_window_15min: int = 2880
    long_term_window_hourly: int = 720

    min_daily_reference_samples: int = 7
    min_weekly_reference_samples: int = 4

    trend_threshold: float = 0.30
    min_reference_power_w: float = 10.0

    min_reference_samples: int = 100
    min_residual_std_w: float = 1.0
    unusual_threshold: float = 2.0
    strong_anomaly_threshold: float = 3.0