from dataclasses import dataclass


@dataclass(frozen=True)
class NumericalAnalysisConfig:
    short_term_window_15min: int = 12
    short_term_window_hourly: int = 3

    long_term_window_15min: int = 2880
    long_term_window_hourly: int = 720

    min_daily_reference_samples: int = 7
    min_weekly_reference_samples: int = 4

    trend_threshold: float = 0.10
    
    min_reference_samples: int = 100
    unusual_threshold: float = 2.0
    strong_anomaly_threshold: float = 3.0