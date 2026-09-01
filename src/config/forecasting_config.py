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


DEFAULT_PROPHET_VARIANTS: tuple[ProphetVariantConfig, ...] = (
    # P0 bleibt deaktiviert, bis die Proposal-Saisonalität definiert ist.
    # ProphetVariantConfig(
    #     model_id="P0",
    #     history_mode="rolling",
    #     rolling_window_hours=7 * 24,
    #     retraining_interval_hours=24,
    #     # Zusätzliche Proposal-Saisonalität noch offen.
    # ),
    ProphetVariantConfig(
        model_id="P1",
        history_mode="fixed_train",
        rolling_window_hours=None,
        retraining_interval_hours=None,
    ),
    ProphetVariantConfig(
        model_id="P2",
        history_mode="expanding",
        rolling_window_hours=None,
        retraining_interval_hours=24,
    ),
    ProphetVariantConfig(
        model_id="P3",
        history_mode="rolling",
        rolling_window_hours=7 * 24,
        retraining_interval_hours=24,
    ),
    ProphetVariantConfig(
        model_id="P4",
        history_mode="expanding",
        rolling_window_hours=None,
        retraining_interval_hours=24,
        weekly_seasonality=True,
    ),
    ProphetVariantConfig(
        model_id="P5",
        history_mode="rolling",
        rolling_window_hours=28 * 24,
        retraining_interval_hours=24,
    ),
)


@dataclass(frozen=True)
class ForecastingConfig:
    config_version: str = "0.4"

    # Forecast-Ziel
    candidate_id: str = "H1-M54"
    frequency: str = "1h"
    timezone: str = "UTC"
    horizon_hours: int = 24

    # Walk-Forward-Evaluation
    forecast_origin_step_hours: int = 24
    complete_horizons_only: bool = True

    # Vergleichsvarianten
    baseline_model_ids: tuple[str, ...] = ("B1", "B2", "B3")
    prophet_variants: tuple[ProphetVariantConfig, ...] = (
        DEFAULT_PROPHET_VARIANTS
    )

    # Gemeinsame Prophet-Konfiguration
    growth: str = "linear"
    daily_seasonality: bool = True
    yearly_seasonality: bool = False
    interval_width: float = 0.80

    # Evaluation
    metrics: tuple[MetricName, ...] = ("mae", "rmse", "mape")
    primary_metric: MetricName = "mae"
    exclude_imputed_targets: bool = True
    mape_positive_targets_only: bool = True

    # Erst nach der Validation festlegen und vor dem Test einfrieren.
    primary_naive_reference: str | None = None

    # Rohprognosen müssen unabhängig davon erhalten bleiben.
    negative_forecast_handling: NegativeForecastHandling = "raw"