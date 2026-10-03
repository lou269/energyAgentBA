from dataclasses import dataclass, field, replace

from experiments.common.standard_config import COLDSTART_DAYS
from src.config.config_forecasting import (
    C2_EXPANDING,
    C3_ROLLING_30,
    ExperimentSplit,
    FORECAST_MODEL_PROPHET_VARIANTS,
    ForecastingConfig,
    ProphetVariantConfig,
)

RUN_PREFIX = "k1"
SEASONALITY_RUN_PREFIX = "k1_season"
# vom Runner geschrieben, vom Report gelesen, die übrigen Ergebnisdateien kommen aus run_forecast_comparison
REFERENCE_FILE = "primary_naive_reference"
SEASONALITY_METRICS_FILE = "origin_metrics"

# unterscheidet sich von C2 nur in der Jahressaisonalität
S1_EXPANDING_YEARLY = replace(C2_EXPANDING, model_id="S1", yearly_seasonality=True)

# Ordnerendung je Split, k1_001 liegt schon unter rolling_val/macro_val
SPLIT_DIRECTORY_SUFFIX: dict[str, str] = {"validation": "val", "test": "test"}


@dataclass(frozen=True)
class K1Config(ForecastingConfig):
    config_version: str = "forecast-model-0.1"
    experiment_id: str = "K1_forecast_model"
    split: ExperimentSplit = "validation"

    comparison_modes: tuple[str, ...] = ("rolling", "macro")
    # Historie vor Split-Start: rolling wie der Online-Zyklus, macro alles davor (70/15/15)
    mode_history_days: dict[str, int | None] = field(
        default_factory=lambda: {"rolling": COLDSTART_DAYS, "macro": None}
    )

    prophet_variants: tuple[ProphetVariantConfig, ...] = FORECAST_MODEL_PROPHET_VARIANTS

    # C1 als Referenz dazu, damit der Skill auch zeigt, was Retraining gegenüber dem statischen Modell bringt
    reference_model_ids: tuple[str, ...] = ("B1", "B2", "B3", "C1")

    # Jahressaisonalität (früher E3 Teil A): ein volles Jahr Prognose, davor gut ein Jahr Historie ab Datenbeginn (01.04.2013).
    # Liegt ganz im Train-Split (bis 29.04.2015), auf der Validierung reicht die Länge nicht für ein Jahr
    seasonality_split: str = "train"
    seasonality_start_date: str = "2014-04-15"
    seasonality_days: int = 365
    seasonality_variants: tuple[ProphetVariantConfig, ...] = (
        C3_ROLLING_30,
        C2_EXPANDING,
        S1_EXPANDING_YEARLY,
    )
    # (Variante, Referenz): Jahressaisonalität allein, längere Historie allein, beides gegen das produktive Modell
    seasonality_comparisons: tuple[tuple[str, str], ...] = (
        ("S1", "C2"),
        ("C2", "C3_30"),
        ("S1", "C3_30"),
    )
