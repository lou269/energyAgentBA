from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


HistoryMode = Literal["fixed_train", "expanding", "rolling"]
NegativeForecastHandling = Literal["raw", "clip_zero"]
MetricName = Literal["mae", "rmse", "mape"]


@dataclass(frozen=True)
class ProphetVariantConfig:
    model_id: str
    history_mode: HistoryMode
    rolling_window_hours: int | None
    retraining_interval_hours: int | None
    weekly_seasonality: bool = False


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
    timezone: str = "UTC"
    horizon_hours: int = 24

    # Walk-Forward-Evaluation
    forecast_origin_step_hours: int = 24
    complete_horizons_only: bool = True

    # Naive Baselines
    baseline_model_ids: tuple[str, ...] = ("B1", "B2", "B3")

    # Gemeinsame Prophet-Konfiguration
    growth: str = "linear"
    daily_seasonality: bool = True
    yearly_seasonality: bool = False
    interval_width: float = 0.80
    uncertainty_samples: int = 1000
    seed: int = 42

    primary_naive_reference: str | None = None
    negative_forecast_handling: NegativeForecastHandling = "raw"