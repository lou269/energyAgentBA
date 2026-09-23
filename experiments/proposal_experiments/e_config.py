from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.config_forecasting import ExperimentSplit, ForecastingConfig, ProphetVariantConfig

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"


''' E1 - NEUES GERÄT '''
@dataclass(frozen=True)
class E1Config:
    device_meter_key: str = "H1_M9"  # HTPC, siehe channel_registry.csv appliances

    cutover_time: str | None = "2014-04-15T00:00:00+00:00"

    margin_before_days: int = 14
    margin_after_days: int = 14


''' E2 - ABWESENHEIT '''
@dataclass(frozen=True)
class E2Config:
    calendar_events_file: Path = SCENARIOS_DIR / "calendar_events.json"

    active_absence_event_id: str = "vacation-2013-06"

    decision_time_margin_before_days: int = 7
    decision_time_margin_after_days: int = 4

    min_coverage_share_for_subtraction: float = 0.9


''' E3 - SAISONALE DRIFT '''
@dataclass(frozen=True)
class E3Config:
    # Übergang Herbst -> Winter, liegt im produktiven Kandidaten (H1-M54-S2, 2013-04-01..2014-07-21)
    observation_window_start: str = "2013-09-01T00:00:00+00:00"
    observation_window_end: str = "2013-12-15T00:00:00+00:00"

    margin_before_days: int = 7
    margin_after_days: int = 0


''' E3 - SAISONALITÄT (Teilfrage 1, Sommer/Winter-Prognosegüte) '''
@dataclass(frozen=True)
class E3DataConfig:
    # deckt Sommer 2013, Winter 2013/14 und Frühling/Sommer 2014 ab, kein volles zweites Jahr
    # (Kandidat endet 2014-07-21) aber ein kompletter Saisonzyklus
    test_window_start: str = "2013-06-01T00:00:00+00:00"
    test_window_end: str = "2014-07-20T00:00:00+00:00"


''' E4 - KALTSTART (Teil a, Prognose) '''
@dataclass(frozen=True)
class E4Config:
    # je eine Jahreszeit im Train-Split, wie K3, nur Winter einen Monat später: ab 15.01. läge Weihnachten in der CS30-Historie, nicht aber in CS7
    start_dates: tuple[str, ...] = ("2013-10-15", "2014-02-15", "2014-04-15", "2014-07-15")

    # C3_30 sieht nie mehr als 30 Tage, CS30 ist damit schon der eingeschwungene Zustand
    coldstart_days: tuple[int, ...] = (7, 14, 30)

    evaluation_days: int = 56

    # Tages-MAEs schwanken stark, die Lernkurve wird kausal über so viele Tage gemittelt
    smoothing_days: int = 7

    window_edges_days: tuple[int, ...] = (7, 14, 28, 56)


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
