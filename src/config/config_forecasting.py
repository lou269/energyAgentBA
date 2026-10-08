from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProductionGapMethod = Literal["ffill", "none"]
HistoryMode = Literal["fixed_train", "expanding", "rolling"]
LLMMode = Literal["off", "rule", "real"]


@dataclass(frozen=True)
class SplitDefinition:
    window: str  # Datenspanne, in der der Abschnitt liegt
    days: int | None  # Länge in lokalen Kalendertagen, None = Rest


# Abschnitte in zeitlicher Reihenfolge. train ist nur Historie, ein Jahr für die Jahressaisonalität in K4, die am Anfang von validation beginnt.
# Eingestellt wird in validation, getestet im späteren Fenster test
SPLITS: dict[str, SplitDefinition] = {
    "train": SplitDefinition(window="development", days=365),
    "validation": SplitDefinition(window="development", days=None),
    "test": SplitDefinition(window="test", days=None),
}

""" PREPROCESSING """


@dataclass(frozen=True)
class PreprocessingConfig:
    gap_treatment_method: ProductionGapMethod = "ffill"
    max_imputation_gap_hourly: int = 3

    stuck_value_min_hours: float = 6.0

    max_daily_missing_share: float = 0.10


""" NUMERICAL ANALYSIS """


@dataclass(frozen=True)
class NumericalAnalysisConfig:
    sample_period_hours_hourly: float = 1.0

    min_daily_reference_samples: int = 7
    min_weekday_reference_samples: int = 4

    min_reference_power_w: float = 10.0

    min_residual_std_w: float = 1.0

    # Einzeltag-Alarm und Median/MAD statt Mittelwert/σ
    # weekly/long_term sind Rollmittel und bleiben nach einer Verschiebung wochenlang erhöht -> zählen nur über ihre Streaks
    single_day_scales: tuple[str, ...] = ("daily", "weekday")

    unusual_threshold: float = 3.4
    # Streak-Schwellen: kalibriert in K1
    weekly_streak_threshold: float = 1.02
    long_term_streak_threshold_pct: float = 14.2

    # new_pattern nur aus weekly und longterm
    level_shift_scales: tuple[str, ...] = ("weekly", "long_term")
    min_sustained_scales: int = 2

    long_term_window_days: int = 28
    weekly_window_days: int = 7

    # Mindestabdeckung für weekly_mean/long_term_window_mean (rolling): ein einzelner NaN-Tag (z.B. measurement_error)
    rolling_window_min_coverage: float = 0.8

    long_term_reference_days: int = 28

    reference_window_rolling_days: int = 60

    # weekly: Anzahl 7-Tage-Mittel in der Referenz, long_term: gültige Tage im Referenzfenster
    min_weekly_reference_samples: int = 1
    min_longterm_reference_samples: int = 14

    # Fenstergröße für scale_anomaly_streak_days: wie viele Tage zurück gezählt wird
    streak_tolerance_window_days: int = 7

    # Mindest-Treffer innerhalb von streak_tolerance_window_days, damit eine Skala als sustained gilt (anomaly_detection.py)  (unkalibriert)
    sustained_anomaly_streak_days: int = 6


""" PROPHET """


@dataclass(frozen=True)
class ProphetVariantConfig:
    model_id: str
    history_mode: HistoryMode
    rolling_window_days: int | None
    retraining_interval_days: int | None
    weekly_seasonality: bool = False
    yearly_seasonality: bool = False


C1_STATIC = ProphetVariantConfig(
    model_id="C1",
    history_mode="fixed_train",
    rolling_window_days=None,
    retraining_interval_days=None,
)

C2_EXPANDING = ProphetVariantConfig(
    model_id="C2",
    history_mode="expanding",
    rolling_window_days=None,
    retraining_interval_days=1,
)

C3_ROLLING_7 = ProphetVariantConfig(
    model_id="C3_7",
    history_mode="rolling",
    rolling_window_days=7,
    retraining_interval_days=1,
)

C3_ROLLING_30 = ProphetVariantConfig(
    model_id="C3_30",
    history_mode="rolling",
    rolling_window_days=30,
    retraining_interval_days=1,
)

C3_ROLLING_60 = ProphetVariantConfig(
    model_id="C3_60",
    history_mode="rolling",
    rolling_window_days=60,
    retraining_interval_days=1,
)

FORECAST_MODEL_PROPHET_VARIANTS: tuple[ProphetVariantConfig, ...] = (
    C1_STATIC,
    C2_EXPANDING,
    C3_ROLLING_7,
    C3_ROLLING_30,
    C3_ROLLING_60,
)

MODEL_LABELS: dict[str, str] = {
    "B1": "B1 naiv, letzter Wert",
    "B2": "B2 naiv, Vortag",
    "B3": "B3 naiv, Vorwoche",
    "C1": "C1 statisch",
    "C2": "C2 expanding",
    "C3_7": "C3_7 rolling 7 Tage",
    "C3_30": "C3_30 rolling 30 Tage",
    "C3_60": "C3_60 rolling 60 Tage",
}

selected_prophet_model = C3_ROLLING_30
""" FORECASTING """


@dataclass(frozen=True)
class ForecastingConfig:
    config_version: str = "0.5"

    selected_prophet_variant: ProphetVariantConfig = selected_prophet_model

    experiment_id: str = "forecasting"

    # Forecast-Ziel
    frequency: str = "1h"

    # ganze lokale Kalendertage ab Mitternacht
    horizon_days: int = 1

    # Walk-Forward-Evaluation
    forecast_origin_step_days: int = 1

    cycle_coldstart_days: int = 60

    # Naive Baselines
    baseline_model_ids: tuple[str, ...] = ("B1", "B2", "B3")

    # Gemeinsame Prophet-Konfiguration
    growth: str = "linear"
    daily_seasonality: bool = True
    country_holidays: str | None = "UK"
    weekly_seasonality: bool = False
    # aus: im Log-Raum liefert exp() eher den Median, das Tagesmittel lag in K4 um gut 10 % zu tief, Tagesfehler ohne Log gleich gut
    log_transform: bool = False
    interval_width: float = 0.80
    uncertainty_samples: int = 1000
    seed: int = 42

    # aus dem K4-Validierungslauf übertragen, gilt für Test-Split und E4
    primary_naive_reference: str | None = "B2"
    # ohne Log kann Prophet unter 0 W prognostizieren
    clip_negative_forecasts: bool = True

    # unter diesem Wert bläht MAPE durch Division nahe 0 unkontrolliert auf
    mape_min_eligible_watts: float = 10.0


""" LLM """


@dataclass(frozen=True)
class LLMConfig:
    model: str = "ministral-3:8b"  # in K2 gewählt
    prompt_version: str = "v30"
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
    # CTX2: das LLM holt den Kalender per Function Calling selbst, im selben Fenster wie CTX1
    calendar_tool: bool = False
    # nur für die Abruf-Entscheidung, eingeordnet wird danach mit prompt_version
    calendar_tool_prompt_version: str = "tool_v30"


@dataclass(frozen=True)
class TextCheckConfig:
    control_words: tuple[str, ...] = (
        "schalte",
        "ausschalt",
        "abschalt",
        "einschalt",
        "ausstecken",
        "abstecken",
        "verschieb",
        "sparen",
        "einspar",
    )
    # erlaubte Abweichung einer genannten Zahl von den Zahlen im State (Rundung im Text)
    number_tolerance: float = 0.5
    # auf diese Stufe gerundete Zahlen („etwa 70 %“) dürfen um die halbe Stufe abweichen
    rounding_step: float = 10.0


@dataclass(frozen=True)
class ComparisonConfig:
    max_consecutive_llm_failures: int = 5
    max_total_llm_failures: int = 15
    calendar_lookback_days: int = 1
    calendar_lookahead_days: int = 1


@dataclass(frozen=True)
class CycleConfig:
    forecasting_config: ForecastingConfig
    numerical_analysis_config: NumericalAnalysisConfig
    event_adaptation: bool
    llm_mode: LLMMode
    llm_config: LLMConfig | None = None
    # absence (Kalenderfenster) und measurement_error (Tag) aus Training und Referenz, aus nur für den E2-Vergleich
    window_exclusion: bool = True


SYS_VARIANTS: dict[str, CycleConfig] = {
    "SYS0": CycleConfig(
        forecasting_config=ForecastingConfig(selected_prophet_variant=C1_STATIC),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=False,
        llm_mode="off",
    ),
    # ordnet wie SYS2 ein, adaptiert nie
    "SYS1": CycleConfig(
        forecasting_config=ForecastingConfig(
            selected_prophet_variant=selected_prophet_model
        ),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=False,
        llm_mode="rule",
    ),
    "SYS2": CycleConfig(
        forecasting_config=ForecastingConfig(
            selected_prophet_variant=selected_prophet_model
        ),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="rule",
    ),
    "SYS3": CycleConfig(
        forecasting_config=ForecastingConfig(
            selected_prophet_variant=selected_prophet_model
        ),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="real",
        llm_config=LLMConfig(),
    ),
    # holt den Kalender per Function Calling selbst (E2, CTX2)
    "SYS3_TOOL": CycleConfig(
        forecasting_config=ForecastingConfig(
            selected_prophet_variant=selected_prophet_model
        ),
        numerical_analysis_config=NumericalAnalysisConfig(),
        event_adaptation=True,
        llm_mode="real",
        llm_config=LLMConfig(calendar_tool=True),
    ),
}

SYS_LABELS: dict[str, str] = {
    "SYS0": "SYS0 statisch, ohne Adaption",
    "SYS1": "SYS1 ohne Adaption",
    "SYS2": "SYS2 Regel",
    "SYS3": "SYS3 LLM",
    "SYS3_TOOL": "SYS3 LLM, Kalender per Tool",
}
