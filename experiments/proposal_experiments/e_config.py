from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config.config_forecasting import (
    ExperimentSplit,
    ForecastingConfig,
    ProphetVariantConfig,
)

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"

# Meldung = Tag, zu dem der Nutzer eine Erklärung bekäme (in SYS3 ein LLM-Aufruf), gilt auch für die K-Studien
NOTIFICATION_CLASSIFICATIONS: tuple[str, ...] = (
    "peak",
    "low",
    "new_pattern",
    "absence",
)
NOTIFICATION_PERIOD_DAYS = 30


""" E1 - NEUES GERÄT """


@dataclass(frozen=True)
class E1Config:
    device_selection_subdir: Path = Path("device_selection")

    reference_config: str = "SYS1"
    target_classification: str = "new_pattern"

    # Waschtrockner, größter Anteil am Mains-Verbrauch (e1_device_check)
    device_meter_keys: tuple[str, ...] = ("H1_M5",)

    # lokales Datum, wird über local_midnight_utc() zur Mitternacht Ortszeit Cutover, nach dem H1_M5 den größten Anteil an Mains hat (e1_device_check)
    cutover_date: str = "2014-03-24"

    margin_before_days: int = 14
    # new_pattern braucht frühestens 6 Treffer im 7-Tage-Fenster, danach bleiben rund 3 Wochen, um die Adaption zu bewerten
    margin_after_days: int = 28

    # Cutover-Kandidaten alle 4 Wochen, damit jeder auf denselben Wochentag fällt
    cutover_step_days: int = 28
    min_device_coverage: float = 0.9


""" E2 - ABWESENHEIT """


@dataclass(frozen=True)
class E2Config:
    calendar_events_file: Path = SCENARIOS_DIR / "calendar_events.json"

    active_absence_event_id: str = "vacation-2013-06"

    decision_time_margin_before_days: int = 7
    decision_time_margin_after_days: int = 4

    min_coverage_share_for_subtraction: float = 0.9


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


""" E4 - KALTSTART (Teil a, Prognose) """


@dataclass(frozen=True)
class E4Config:
    # je eine Jahreszeit im Train-Split, wie K3, nur Winter einen Monat später: ab 15.01. läge Weihnachten in der CS30-Historie, nicht aber in CS7
    start_dates: tuple[str, ...] = (
        "2013-10-15",
        "2014-02-15",
        "2014-04-15",
        "2014-07-15",
    )

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
