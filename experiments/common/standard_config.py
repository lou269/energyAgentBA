from __future__ import annotations

from dataclasses import dataclass, field

from src.config.config_forecasting import (
    ForecastingConfig,
    NumericalAnalysisConfig,
    PreprocessingConfig,
)
from src.config.project_config import ProjectConfig

# für alle Studien gleich, wird deshalb nicht durch die Funktionen gereicht
PROJECT_CONFIG = ProjectConfig()
LOCAL_TIMEZONE = PROJECT_CONFIG.timezone

# Kaltstart des Online-Zyklus vor dem ersten Entscheidungstag
COLDSTART_DAYS = ForecastingConfig().cycle_coldstart_days
# für die Festhänger-Flags nach der Vorverarbeitung eingebauter Reihen, dieselbe Regel wie bei den echten Daten
STUCK_VALUE_MIN_HOURS = PreprocessingConfig().stuck_value_min_hours
HOURLY_SAMPLE_PERIOD_HOURS = NumericalAnalysisConfig().sample_period_hours_hourly

# Meldung = Tag, zu dem der Nutzer eine Erklärung bekäme (in SYS3 ein LLM-Aufruf) (low und absence brauchen keine Meldung)
# measurement_error schon, Zähler und Anschluss kann nur der Haushalt prüfen
NOTIFICATION_CLASSIFICATIONS: tuple[str, ...] = (
    "peak",
    "new_pattern",
    "measurement_error",
)
NOTIFICATION_PERIOD_DAYS = 30

# Rollen der Systemvarianten in allen Studien: Referenz ohne Adaption, Regel, LLM
REFERENCE_SYSTEM = "SYS1"
RULE_SYSTEM = "SYS2"
LLM_SYSTEM = "SYS3"


# Szenario-Katalog aller Studien. Cutover und Zeitfenster gelten nur für die Komponentenstudien K2 (Ebene 2) und K3,
# Experimente laufen nicht auf diesen Cutovern, weil K2 darauf eingestellt wurde
@dataclass(frozen=True)
class StandardScenarioConfig:
    decimals: int = 1
    # Abschnitt, in dem die Standard-Cutover liegen
    split: str = "validation"
    # lokale Kalendertage in validation -> Entscheidungstage der Fenster (Überwachung davor bis margin_after_days danach) überlappen sich nicht
    # keines enthält Weihnachten und Neujahr
    cutover_dates: dict[str, str] = field(
        default_factory=lambda: {
            "CO1": "2014-07-15",  # Sommer zum Herbst
            "CO2": "2014-10-24",  # Herbstanstieg
            "CO3": "2015-03-01",  # Winterende, ohne echtes Ereignis
            "CO4": "2015-06-10",  # Frühsommer, ohne echtes Ereignis
            "CO5": "2015-10-22",  # Herbstanstieg im zweiten Jahr
        }
    )

    # Historie beginnt Kaltstart + diese Tage vor dem Cutover
    monitoring_before_cutover_days: int = 40
    margin_after_days: int = 60

    # Niveauänderungen -> neues Muster = mindestens 20 % in 28 Tagen, in beide Richtungen
    # scaled sofort, ramp_28 gerade noch ein Ereignis, ramp_56 mit 10 % je 28 Tage keins
    scale_factor: float = 1.2
    scale_factor_down: float = 0.8
    ramp_fast_days: int = 28
    ramp_slow_days: int = 56

    # Einzeltage am 99-%-Quantil echter Tage (development):
    # peak ab 17 Uhr konzentriert, sieht vor allem daily, level gleichmäßig über den Tag, sieht nur weekday
    peak_extra_w: float = 670.0
    peak_start_hour: int = 17
    peak_hours: int = 6
    level_extra_w: float = 190.0

    # nur für K2 Ebene 2 (Modellwahl, kein Beleg): deutlich über der Grenze, damit das Gate sicher öffnet und es etwas einzuordnen gibt
    strong_scale_factor: float = 1.3
    strong_peak_extra_w: float = 1000.0

    # mehr als stuck_value_min_hours (6 h), sonst markiert die Plausibilitätsprüfung nichts
    stuck_hours: int = 12


STANDARD_CONFIG = StandardScenarioConfig()


# Szenario-Art -> erwartete Klasse, vor den Läufen festgelegt. absence (G2) kommt aus E2.
# Langsame Rampen sind nach der Definition kein Ereignis, still aufgenommen ist richtig, ein Reset ein Fehler
GOLDSTANDARD_EXPECTED: dict[str, str] = {
    "control": "normal",
    "scaled": "new_pattern",
    "scaled_strong": "new_pattern",
    "ramp_28": "new_pattern",
    "ramp_28_down": "new_pattern",
    "ramp_56": "normal",
    "ramp_56_down": "normal",
    "peak": "peak",
    "peak_strong": "peak",
    "level": "peak",
    "absence": "absence",
    "stuck": "measurement_error",
}

# was der Vorfilter bei der erwarteten Klasse tun soll, gilt für jede Studie mit Katalog-Arten
EXPECTED_DETECTION: dict[str, str] = {
    "new_pattern": "reset",
    "peak": "alarm",
    "normal": "silent",
    "measurement_error": "flag",
}
