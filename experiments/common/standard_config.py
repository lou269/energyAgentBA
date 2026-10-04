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
# Nachkommastellen in ergebnis.md und den Ergebnis-CSVs
DECIMALS = PROJECT_CONFIG.result_decimals
# Kaltstart des Online-Zyklus vor dem ersten Entscheidungstag
COLDSTART_DAYS = ForecastingConfig().cycle_coldstart_days
# für die Festhänger-Flags nach der Vorverarbeitung eingebauter Reihen, dieselbe Regel wie bei den echten Daten
STUCK_VALUE_MIN_HOURS = PreprocessingConfig().stuck_value_min_hours
HOURLY_SAMPLE_PERIOD_HOURS = NumericalAnalysisConfig().sample_period_hours_hourly

# Meldung = Tag, zu dem der Nutzer eine Erklärung bekäme (in SYS3 ein LLM-Aufruf)
NOTIFICATION_CLASSIFICATIONS: tuple[str, ...] = (
    "peak",
    "low",
    "new_pattern",
    "absence",
)
NOTIFICATION_PERIOD_DAYS = 30

# Rollen der Systemvarianten in allen Studien: Referenz ohne Adaption, Regel, LLM
REFERENCE_SYSTEM = "SYS1"
RULE_SYSTEM = "SYS2"
LLM_SYSTEM = "SYS3"


# Standard-Szenarien der Komponentenstudien K2, K3 (Ebene 2) und K4. Experimente laufen nicht auf diesen Cutovern, weil K2 und K3 darauf eingestellt wurden
@dataclass(frozen=True)
class StandardScenarioConfig:
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

    # Standard-Stufe "step", weitere Stärken über den Namen (step_30 = +30 W)
    step_injection_w: float = 100.0

    # alles ab Cutover um 30 % höher, im Mittel nach den Cutovern etwa ebenfalls +100 W.
    # Additiv gegen multiplikativ, der Stufen-Regressor in K4 lernt wegen log_transform einen Faktor.
    # Zugleich Endniveau der Rampen (ramp_28 = in 28 Tagen auf diesen Faktor)
    scale_factor: float = 1.3
    # dasselbe nach unten, Arten mit Endung _down (scaled_down, ramp_28_down)
    scale_factor_down: float = 0.7

    # peak: einmalige Zusatzlast am Cutover-Tag ab 17 Uhr, über 3 Stunden im Tagesmittel etwa +125 W (in Haus 1 alle 3 Wochen normal),
    # weitere Dauern über den Namen (peak_6 = 6 Stunden, Tagesmittel +250 W, über dem 99-%-Quantil echter Tage)
    peak_extra_w: float = 1000.0
    peak_start_hour: int = 17
    peak_hours: int = 3

    # stuck: ab lokaler Mitternacht des Cutover-Tags hängt der letzte Wert des Vortags so lange fest, mehr als stuck_value_min_hours (6 h), sonst markiert die Plausibilitätsprüfung nichts
    stuck_hours: int = 12


STANDARD_CONFIG = StandardScenarioConfig()


# Szenario-Art (ohne Stärke) -> erwartete Klasse, vor den Läufen festgelegt. absence (G2) kommt aus E2, stuck (G5) nur aus E5.
# ramp (G4, nach E3 Teil B): öffnet eine Saisonverschiebung das Gate, ist new_pattern mit Reset richtig, still aufgenommen zählt wie control
GOLDSTANDARD_EXPECTED: dict[str, str] = {
    "control": "normal",
    "step": "new_pattern",
    "ramp": "new_pattern",
    "absence": "absence",
    "peak": "peak",
    "stuck": "measurement_error",
}
