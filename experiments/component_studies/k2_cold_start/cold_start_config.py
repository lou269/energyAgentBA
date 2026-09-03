from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.config.forecasting_config import ForecastingConfig, ProphetVariantConfig


ExperimentSplit = Literal["validation", "test"]


COLD_START_PROPHET_VARIANTS: tuple[ProphetVariantConfig, ...] = (
    ProphetVariantConfig(
        model_id="C1",
        history_mode="fixed_train",
        rolling_window_hours=None,
        retraining_interval_hours=None,
    ),
    ProphetVariantConfig(
        model_id="C2",
        history_mode="expanding",
        rolling_window_hours=None,
        retraining_interval_hours=24,
    ),
    ProphetVariantConfig(
        model_id="C3",
        history_mode="rolling",
        rolling_window_hours=7 * 24,
        retraining_interval_hours=24,
    ),
)


@dataclass(frozen=True)
class ColdStartExperimentConfig(ForecastingConfig):
    """Konfiguration für K2: Cold Start und reguläres Retraining."""

    config_version: str = "cold-start-0.1"
    experiment_id: str = "K2_cold_start"
    split: ExperimentSplit = "validation"

    # Vor dem jeweiligen Experimentlauf festlegen 
    data_start: str | None = None
    data_end: str | None = None

    # erster Forecast nach sieben vollständigen Tagen -> Proposal 
    initial_history_hours: int = 7 * 24

    prophet_variants: tuple[ProphetVariantConfig, ...] = (COLD_START_PROPHET_VARIANTS)

    output_subdir: str = "cold_start"