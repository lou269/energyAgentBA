from __future__ import annotations

from dataclasses import dataclass

from src.config.config_forecasting import (
    ExperimentSplit,
    ForecastingConfig,
    ProphetVariantConfig,
)


""" E3 - SAISONALE DRIFT """


@dataclass(frozen=True)
class E3Config:
    # Übergang Herbst -> Winter, liegt im produktiven Kandidaten (H1-M54-S2, 2013-04-01..2014-07-21)
    observation_window_start_date: str = "2013-09-01"
    observation_window_end_date: str = "2013-12-15"

    margin_before_days: int = 7
    margin_after_days: int = 0


""" E3 - SAISONALITÄT (Teilfrage 1, Sommer/Winter-Prognosegüte) """


@dataclass(frozen=True)
class E3DataConfig:
    # deckt Sommer 2013, Winter 2013/14 und Frühling/Sommer 2014 ab, kein volles zweites Jahr
    # (Kandidat endet 2014-07-21) aber ein kompletter Saisonzyklus
    test_window_start_date: str = "2013-06-01"
    # exklusiv, letzter ausgewerteter Tag ist der 19.07.
    test_window_end_date: str = "2014-07-20"


# weekly fix auf True (wie produktives C2), nur yearly wird zwischen S0/S1 verglichen
_S0 = ProphetVariantConfig(
    model_id="S0",
    history_mode="expanding",
    rolling_window_days=None,
    retraining_interval_days=1,
    weekly_seasonality=True,
    yearly_seasonality=False,
)
_S1 = ProphetVariantConfig(
    model_id="S1",
    history_mode="expanding",
    rolling_window_days=None,
    retraining_interval_days=1,
    weekly_seasonality=True,
    yearly_seasonality=True,
)

SEASONALITY_PROPHET_VARIANTS: tuple[ProphetVariantConfig, ...] = (_S0, _S1)


@dataclass(frozen=True)
class SeasonalityExperimentConfig(ForecastingConfig):
    config_version: str = "seasonality-0.1"
    experiment_id: str = "E3"
    split: ExperimentSplit = "test"

    data: E3DataConfig = E3DataConfig()

    prophet_variants: tuple[ProphetVariantConfig, ...] = SEASONALITY_PROPHET_VARIANTS

    output_subdir: str = "seasonality"
