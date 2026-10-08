from dataclasses import dataclass, field, replace

from experiments.common.standard_config import COLDSTART_DAYS
from src.config.config_forecasting import (
    C2_EXPANDING,
    C3_ROLLING_30,
    FORECAST_MODEL_PROPHET_VARIANTS,
    ForecastingConfig,
    ProphetVariantConfig,
)

RUN_PREFIX = "k4"
SEASONALITY_RUN_PREFIX = "k4_season"
# vom Runner geschrieben, vom Report gelesen, die übrigen Ergebnisdateien kommen aus run_forecast_comparison
REFERENCE_FILE = "primary_naive_reference"
SEASONALITY_FORECASTS_FILE = "forecasts"

# unterscheidet sich von C2 nur in der Jahressaisonalität
Y1_EXPANDING_YEARLY = replace(C2_EXPANDING, model_id="Y1", yearly_seasonality=True)

# Ordnerendung je Split, k4_001 liegt schon unter rolling_val/macro_val
SPLIT_DIRECTORY_SUFFIX: dict[str, str] = {"validation": "val", "test": "test"}


@dataclass(frozen=True)
class K4Config(ForecastingConfig):
    config_version: str = "forecast-model-0.1"
    experiment_id: str = "K4_forecast_model"
    split: str = "validation"

    comparison_modes: tuple[str, ...] = ("rolling", "macro")
    # Historie vor Split-Start: rolling wie der Online-Zyklus, macro alles davor
    mode_history_days: dict[str, int | None] = field(
        default_factory=lambda: {"rolling": COLDSTART_DAYS, "macro": None}
    )

    prophet_variants: tuple[ProphetVariantConfig, ...] = FORECAST_MODEL_PROPHET_VARIANTS

    # C1 als Referenz dazu, damit der Skill auch zeigt, was Retraining gegenüber dem statischen Modell bringt
    reference_model_ids: tuple[str, ...] = ("B1", "B2", "B3", "C1")

    # Jahressaisonalität: volles Jahr Prognose ab Beginn des Abschnitts, davor ein Jahr Historie (train)
    seasonality_days: int = 365
    seasonality_variants: tuple[ProphetVariantConfig, ...] = (
        C3_ROLLING_30,
        C2_EXPANDING,
        Y1_EXPANDING_YEARLY,
    )
    # (Variante, Referenz): Jahressaisonalität allein, längere Historie allein, beides gegen das produktive Modell
    seasonality_comparisons: tuple[tuple[str, str], ...] = (
        ("Y1", "C2"),
        ("C2", "C3_30"),
        ("Y1", "C3_30"),
    )
