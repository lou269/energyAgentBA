from dataclasses import dataclass

from src.config.config_forecasting import ExperimentSplit, FORECAST_MODEL_PROPHET_VARIANTS, ForecastingConfig, ProphetVariantConfig

# Ordnerendung je Split, k2_001 liegt schon unter rolling_val/macro_val
SPLIT_DIRECTORY_SUFFIX: dict[str, str] = {"validation": "val", "test": "test"}


@dataclass(frozen=True)
class ForecastModelExperimentConfig(ForecastingConfig):

    config_version: str = "forecast-model-0.1"
    experiment_id: str = "K2_forecast_model"
    split: ExperimentSplit = "validation"

    comparison_modes: tuple[str, ...] = ("rolling", "macro")

    prophet_variants: tuple[ProphetVariantConfig, ...] = FORECAST_MODEL_PROPHET_VARIANTS

    # C1 als Referenz dazu, damit der Skill auch zeigt, was Retraining gegenüber dem statischen Modell bringt
    reference_model_ids: tuple[str, ...] = ("B1", "B2", "B3", "C1")