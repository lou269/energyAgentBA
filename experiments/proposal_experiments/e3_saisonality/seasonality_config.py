from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.config.forecasting_config import ForecastingConfig, ProphetVariantConfig


ExperimentSplit = Literal["validation", "test"]


SEASONALITY_PROPHET_VARIANTS: tuple[ProphetVariantConfig, ...] = (
    ProphetVariantConfig(
        model_id="S0",
        history_mode="expanding",
        rolling_window_hours=None,
        retraining_interval_hours=24,
        weekly_seasonality=False,
    ),
    ProphetVariantConfig(
        model_id="S1",
        history_mode="expanding",
        rolling_window_hours=None,
        retraining_interval_hours=24,
        weekly_seasonality=True,
    ),
)


@dataclass(frozen=True)
class SeasonalityExperimentConfig(ForecastingConfig):
    config_version: str = "seasonality-0.1"
    experiment_id: str = "E2_seasonality"
    split: ExperimentSplit = "validation"

    data_start: str | None = None
    data_end: str | None = None

    prophet_variants: tuple[ProphetVariantConfig, ...] = (SEASONALITY_PROPHET_VARIANTS)

    output_subdir: str = "seasonality"