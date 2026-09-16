from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.config.config_forecasting import ForecastingConfig, ProphetVariantConfig

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"


''' E1 - NEUES GERÄT '''
@dataclass(frozen=True)
class E1Config:
    device_meter_key: str = "H1_M9"  # HTPC, siehe channel_registry.csv appliances
    coldstart_hours: int = 168

    cutover_time: str | None = "2014-04-15T00:00:00+00:00"

    # so viel Historie vor dem Cutover, dass long_term_window_hourly (720h=30 Tage) + Coldstart (168h) beim Cutover-Tag einen validen Referenzwert liefern
    margin_before_days: int = 45
    # bis kurz vor Datenende des Kandidaten (2014-07-21, letzter voller Tag 2014-07-20) statt nur 28 Tage -
    # mehr Beobachtungstage nach dem Cutover, kostet nichts (gleicher Datensatz, ungenutzt)
    margin_after_days: int = 96


''' E2 - ABWESENHEIT '''
@dataclass(frozen=True)
class E2Config:
    calendar_events_file: Path = SCENARIOS_DIR / "calendar_events.json"

    active_absence_event_id: str = "vacation-2013-06"

    decision_time_margin_before_days: int = 7
    decision_time_margin_after_days: int = 4

    # länger als die 7 Tage im Proposal ->  Tages-Anomalieerkennung braucht genug Wochentag-Wiederholungen im Training 
    # (min_weekly_reference_samples braucht mind. 4 desselben Wochentags)
    coldstart_hours: int = 60 * 24

    min_coverage_share_for_subtraction: float = 0.9


''' E3 - SAISONALE DRIFT '''
@dataclass(frozen=True)
class E3Config:
    # Übergang Herbst -> Winter, liegt im produktiven Kandidaten (H1-M54-S2, 2013-04-01..2014-07-21)
    observation_window_start: str = "2013-09-01T00:00:00+00:00"
    observation_window_end: str = "2013-12-15T00:00:00+00:00"

    coldstart_hours: int = 60 * 24  # wie E2, reicht für long_term_window (30 Tage) + genug Wochentag-Wiederholungen

    margin_before_days: int = 7
    margin_after_days: int = 0


''' E3 - SAISONALITÄT (Teilfrage 1, Sommer/Winter-Prognosegüte) '''
@dataclass(frozen=True)
class E3DataConfig:
    # deckt Sommer 2013, Winter 2013/14 und Frühling/Sommer 2014 ab, kein volles zweites Jahr
    # (Kandidat endet 2014-07-21) aber ein kompletter Saisonzyklus
    test_window_start: str = "2013-06-01T00:00:00+00:00"
    test_window_end: str = "2014-07-20T00:00:00+00:00"


ExperimentSplit = Literal["validation", "test"]

# weekly fix auf True (wie produktives C2), nur yearly wird zwischen S0/S1 verglichen
_S0 = ProphetVariantConfig(
    model_id="S0",
    history_mode="expanding",
    rolling_window_hours=None,
    retraining_interval_hours=24,
    weekly_seasonality=True,
    yearly_seasonality=False,
)
_S1 = ProphetVariantConfig(
    model_id="S1",
    history_mode="expanding",
    rolling_window_hours=None,
    retraining_interval_hours=24,
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
