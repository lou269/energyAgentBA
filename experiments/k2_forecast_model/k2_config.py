from dataclasses import dataclass, field

from experiments.common.standard_config import COLDSTART_DAYS
from src.config.config_forecasting import (
    ExperimentSplit,
    FORECAST_MODEL_PROPHET_VARIANTS,
    ForecastingConfig,
    ProphetVariantConfig,
)

RUN_PREFIX = "k2"
# vom Runner geschrieben, vom Report gelesen, die übrigen Ergebnisdateien kommen aus run_forecast_comparison
REFERENCE_FILE = "primary_naive_reference"

# Ordnerendung je Split, k2_001 liegt schon unter rolling_val/macro_val
SPLIT_DIRECTORY_SUFFIX: dict[str, str] = {"validation": "val", "test": "test"}


@dataclass(frozen=True)
class K2Config(ForecastingConfig):
    config_version: str = "forecast-model-0.1"
    experiment_id: str = "K2_forecast_model"
    split: ExperimentSplit = "validation"

    comparison_modes: tuple[str, ...] = ("rolling", "macro")
    # Historie vor Split-Start: rolling wie der Online-Zyklus, macro alles davor (70/15/15)
    mode_history_days: dict[str, int | None] = field(
        default_factory=lambda: {"rolling": COLDSTART_DAYS, "macro": None}
    )

    prophet_variants: tuple[ProphetVariantConfig, ...] = FORECAST_MODEL_PROPHET_VARIANTS

    # C1 als Referenz dazu, damit der Skill auch zeigt, was Retraining gegenüber dem statischen Modell bringt
    reference_model_ids: tuple[str, ...] = ("B1", "B2", "B3", "C1")


MODE_DESCRIPTIONS: dict[str, str] = {
    "rolling": "{coldstart_days} Tage Historie vor Split-Start, wie der Online-Zyklus",
    "macro": "gesamte Historie vor Split-Start",
}
EXCLUSION_LABELS: dict[str, str] = {
    "missing_target": "Messwert fehlt",
    "target_imputed": "imputiert",
}
