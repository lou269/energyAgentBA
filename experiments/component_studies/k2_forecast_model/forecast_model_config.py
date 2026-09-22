from dataclasses import dataclass
from typing import Literal

from src.config.config_forecasting import FORECAST_MODEL_PROPHET_VARIANTS, ForecastingConfig, ProphetVariantConfig


ExperimentSplit = Literal["validation", "test"]


@dataclass(frozen=True)
class ForecastModelExperimentConfig(ForecastingConfig):

    config_version: str = "forecast-model-0.1"
    experiment_id: str = "K2_forecast_model"
    split: ExperimentSplit = "validation"

    prophet_variants: tuple[ProphetVariantConfig, ...] = (FORECAST_MODEL_PROPHET_VARIANTS)