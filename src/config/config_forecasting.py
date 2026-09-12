from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

ProductionGapMethod = Literal["ffill", "none"]
HistoryMode = Literal["fixed_train", "expanding", "rolling"]
NegativeForecastHandling = Literal["raw", "clip_zero"]
MetricName = Literal["mae", "rmse", "mape"]


''' PREPROCESSING '''
@dataclass(frozen=True)
class PreprocessingConfig:
    train_share: float = 0.8
    validation_share: float = 0.1

    gap_treatment_method: ProductionGapMethod = "ffill"
    max_imputation_gap_15min: int = 4
    max_imputation_gap_hourly: int = 6  # nicht das gleiche wie DataPreparationConfig.max_availability_gap_hours

    stuck_value_min_hours: float = 6.0

    lags_15min: tuple[int, ...] = (1, 4, 96, 672)
    lags_hourly: tuple[int, ...] = (1, 24, 168)

    rolling_windows_15min: tuple[int, ...] = (4, 96, 672)
    rolling_windows_hourly: tuple[int, ...] = (24, 168)

    feature_variance_threshold: float = 0.0



''' NUMERICAL ANALYSIS '''
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

    # gegen H1-M54-Train-Split kalibriert (rollierendes 24h-Fenster) - hält die Gesamt-Trigger-Rate
    # nahe an dem, was das frühere Einzelstunden-Gate ergab, statt bei jedem Tagesmaximum auszulösen
    min_elevated_hours_for_gate: float = 4.0

    # Fenstergröße für "Anomalie in den letzten X Stunden" -> steuert aggregate_daily_anomaly,
    # das Adaptionsfenster in adaption_policy.py und die Peak-Timestamp-Grenze im Structured-State-Schema
    anomaly_window_hours: int = 24

    # noch nicht kalibriert -> grob geschätzt als 75% von anomaly_window_hours (18 von 24h).
    # Entscheidet absence vs. new_pattern vs. peak in rule_based_classifier.py
    sustained_daily_elevated_hours: float = 18.0
    multi_scale_minimum: int = 2


''' PROPHET '''
@dataclass(frozen=True)
class ProphetVariantConfig:
    model_id: str
    history_mode: HistoryMode
    rolling_window_hours: int | None
    retraining_interval_hours: int | None
    weekly_seasonality: bool = False


''' FORECASTING '''
@dataclass(frozen=True)
class ForecastingConfig:
    config_version: str = "0.5"

    selected_prophet_variant: ProphetVariantConfig = ProphetVariantConfig(
        model_id="C2",
        history_mode="expanding",
        rolling_window_hours=None,
        retraining_interval_hours=24,
        weekly_seasonality=False,
    )

    experiment_id: str = "forecasting"

    # Forecast-Ziel
    frequency: str = "1h"

    timezone: str = "Europe/London"
    horizon_hours: int = 24

    # Walk-Forward-Evaluation
    forecast_origin_step_hours: int = 24

    # Naive Baselines
    baseline_model_ids: tuple[str, ...] = ("B1", "B2", "B3")

    # Gemeinsame Prophet-Konfiguration
    growth: str = "linear"
    daily_seasonality: bool = True
    yearly_seasonality: bool = False
    country_holidays: str | None = "UK"
    # Prophet fitted auf log(y) statt y, Rücktransformation via exp() nach dem Predict
    log_transform: bool = True
    interval_width: float = 0.80
    uncertainty_samples: int = 1000
    seed: int = 42

    primary_naive_reference: str | None = None
    negative_forecast_handling: NegativeForecastHandling = "raw"

    # unter diesem Wert bläht MAPE durch Division nahe 0 unkontrolliert auf
    mape_min_eligible_watts: float = 10.0


''' LLM '''
@dataclass(frozen=True)
class LLMConfig:
    model: str
    prompt_version: str = "v6"
    temperature: float = 0.0
    seed: int | None = 42
    max_attempts: int = 2
    request_timeout_seconds: float = 120.0
    
    
    