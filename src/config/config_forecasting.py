from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProductionGapMethod = Literal["ffill", "none"]
HistoryMode = Literal["fixed_train", "expanding", "rolling"]
NegativeForecastHandling = Literal["raw", "clip_zero"]
LLMMode = Literal["off", "rule", "real"]

''' PREPROCESSING '''
@dataclass(frozen=True)
class PreprocessingConfig:
    train_share: float = 0.7
    validation_share: float = 0.15

    gap_treatment_method: ProductionGapMethod = "ffill"
    max_imputation_gap_15min: int = 4
    max_imputation_gap_hourly: int = 3  # nicht das gleiche wie DataPreparationConfig.max_availability_gap_hours

    stuck_value_min_hours: float = 6.0

    max_daily_missing_share: float = 0.10


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
    min_weekday_reference_samples: int = 4  # umbenannt von min_weekly_reference_samples (war Wochentags-Groupby in build_daily_cycle_analysis)

    trend_threshold: float = 0.30
    min_reference_power_w: float = 10.0

    min_reference_samples: int = 100
    min_residual_std_w: float = 1.0
    unusual_threshold: float = 2.0
    strong_anomaly_threshold: float = 3.0

    # mindestens 2, sonst waere bei nur 1 verfuegbarer Skala schon diese eine ausreichend - keine echte
    # Mehrskalen-Bestaetigung mehr, nur ein laenger andauernder peak (siehe rule_based_classifier.py)
    min_sustained_scales: int = 2

    # run_cycle rechnet die Anomalieerkennung auf Tagesmittelwerten statt Einzelstunden
    sample_period_hours_daily: float = 24.0
    trend_window_days: int = 7  # unkalibriert, Startwert wie trend_threshold seinerzeit
    long_term_window_days: int = 30
    weekly_window_days: int = 7  # eigenständig von trend_window_days, auch wenn aktuell derselbe Wert

    # Mindestabdeckung für weekly_mean/long_term_window_mean (rolling): ein einzelner NaN-Tag (z.B. measurement_error)
    # soll die Skala nicht gleich für die ganze Fensterlänge lahmlegen, siehe anomalieerkennung_neu.md
    rolling_window_min_coverage: float = 0.8

    # wie viele Tage reference_window_end nach einem Reset noch mitwachsen darf, bevor es einfriert
    max_reference_window_growth_days: int = 60

    # 3-Tage-Fenster ab reference_window_end: train bis reference_window_end-1, Rest validation+test
    reference_window_hours: int = 72

    min_weekly_reference_samples: int = 1
    min_longterm_reference_samples: int = 1

    # Fenstergröße für scale_anomaly_streak_days: wie viele Tage zurück gezählt wird
    streak_tolerance_window_days: int = 7

    # Mindest-Treffer innerhalb von streak_tolerance_window_days, damit eine Skala als sustained gilt und new_pattern statt peak ergibt (rule_based_classifier.py)  (unkalibriert)
    sustained_anomaly_streak_days: int = 6


''' PROPHET '''
@dataclass(frozen=True)
class ProphetVariantConfig:
    model_id: str
    history_mode: HistoryMode
    rolling_window_hours: int | None
    retraining_interval_hours: int | None
    weekly_seasonality: bool = False
    yearly_seasonality: bool = False


C1_STATIC = ProphetVariantConfig(
    model_id="C1",
    history_mode="fixed_train",
    rolling_window_hours=None,
    retraining_interval_hours=None,
)

C2_EXPANDING = ProphetVariantConfig(
    model_id="C2",
    history_mode="expanding",
    rolling_window_hours=None,
    retraining_interval_hours=24,
)

C3_ROLLING_7 = ProphetVariantConfig(
    model_id="C3_7",
    history_mode="rolling",
    rolling_window_hours=7 * 24,
    retraining_interval_hours=24,
)

C3_ROLLING_30 = ProphetVariantConfig(
    model_id="C3_30",
    history_mode="rolling",
    rolling_window_hours=30 * 24,
    retraining_interval_hours=24,
)

C3_ROLLING_60 = ProphetVariantConfig(
    model_id="C3_60",
    history_mode="rolling",
    rolling_window_hours=60 * 24,
    retraining_interval_hours=24,
)

FORECAST_MODEL_PROPHET_VARIANTS: tuple[ProphetVariantConfig, ...] = (
    C1_STATIC,
    C2_EXPANDING,
    C3_ROLLING_7,
    C3_ROLLING_30,
    C3_ROLLING_60
)

selected_prophet_model = C3_ROLLING_30

''' FORECASTING '''
@dataclass(frozen=True)
class ForecastingConfig:
    config_version: str = "0.5"

    selected_prophet_variant: ProphetVariantConfig = selected_prophet_model

    experiment_id: str = "forecasting"

    # Forecast-Ziel
    frequency: str = "1h"

    horizon_hours: int = 24

    # Walk-Forward-Evaluation
    forecast_origin_step_hours: int = 24

    cycle_coldstart_hours: int =  60 * 24

    # Naive Baselines
    baseline_model_ids: tuple[str, ...] = ("B1", "B2", "B3")

    # Gemeinsame Prophet-Konfiguration
    growth: str = "linear"
    daily_seasonality: bool = True
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
    prompt_version: str = "v11"
    temperature: float = 0.0
    # qwen3.5:9b liefert das selbst als Modelfile-Default, gegen Wiederholungsschleifen bei greedy decoding
    presence_penalty: float = 1.5
    seed: int | None = 42
    max_attempts: int = 2
    request_timeout_seconds: float = 120.0
    num_predict: int = 1024
    num_ctx: int = 8192
    think: bool = False
    keep_alive: int | str = "5m"


@dataclass(frozen=True)
class ComparisonConfig:
    max_consecutive_llm_failures: int = 5
    max_total_llm_failures: int = 15
    calendar_lookback_hours: int = 24
    calendar_lookahead_hours: int = 24


@dataclass(frozen=True)
class CycleConfig:
    forecasting_config: ForecastingConfig
    numerical_analysis_config: NumericalAnalysisConfig
    event_adaptation: bool
    llm_mode: LLMMode
    llm_config: LLMConfig | None = None

SYS_VARIANTS: dict[str, CycleConfig] = {
    "SYS0": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=C1_STATIC),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=False,
        llm_mode="off",
    ),
    "SYS1": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=selected_prophet_model),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=False,
        llm_mode="off",
    ),
    "SYS2": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=selected_prophet_model),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="rule",
    ),
    "SYS3": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=selected_prophet_model),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="real",
        llm_config=LLMConfig(model="qwen3:8b"),
    ),
}