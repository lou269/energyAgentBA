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
ANALYSIS_CONFIG = NumericalAnalysisConfig()
LOCAL_TIMEZONE = PROJECT_CONFIG.timezone

# Kaltstart des Online-Zyklus vor dem ersten Entscheidungstag
COLDSTART_DAYS = ForecastingConfig().cycle_coldstart_days
# für die Festhänger-Flags nach der Vorverarbeitung eingebauter Reihen, dieselbe Regel wie bei den echten Daten
STUCK_VALUE_MIN_HOURS = PreprocessingConfig().stuck_value_min_hours
HOURLY_SAMPLE_PERIOD_HOURS = NumericalAnalysisConfig().sample_period_hours_hourly
# Fensterlängen aus der Skalenbeschreibung im Prompt, sie stehen nicht im State, kommen aber in den Antworten vor
PROMPT_WINDOW_NUMBERS = (
    float(ANALYSIS_CONFIG.weekly_window_days),
    float(ANALYSIS_CONFIG.long_term_window_days),
)

# Meldung = Tag, zu dem der Nutzer eine Erklärung bekäme (in SYS3 ein LLM-Aufruf) (low und absence brauchen keine Meldung)
# measurement_error schon, Zähler und Anschluss kann nur der Haushalt prüfen
NOTIFICATION_CLASSIFICATIONS: tuple[str, ...] = (
    "peak",
    "new_pattern",
    "measurement_error",
)
NOTIFICATION_PERIOD_DAYS = 30

# Klassen, nach denen Ereignisse bewertet werden: Einzeltag-Ereignisse am Ereignistag, anhaltende erst mit new_pattern
FLAG_CLASSIFICATION = "measurement_error"
SINGLE_DAY_CLASSIFICATIONS = ("peak", FLAG_CLASSIFICATION)
SUSTAINED_CLASSIFICATION = "new_pattern"

# Rollen der Systemvarianten in allen Studien: Referenz ohne Adaption, Regel, LLM
REFERENCE_SYSTEM = "SYS1"
RULE_SYSTEM = "SYS2"
LLM_SYSTEM = "SYS3"


# Szenario-Katalog aller Studien. Cutover und Zeitfenster gelten nur für die Komponentenstudien K2 (Ebene 2) und K3,
# Experimente laufen nicht auf diesen Cutovern, weil K2 darauf eingestellt wurde
@dataclass(frozen=True)
class StandardScenarioConfig:
    decimals: int = 1
    split: str = "test"
    # lokale Kalendertage je Abschnitt, die Kennungen sind über beide Abschnitte fortlaufend
    # validation: Entscheidungstage der Fenster (Überwachung davor bis margin_after_days danach) überlappen sich nicht,
    # test: Entscheidungstage der Fenster überlappen aber nur Überwachung vorher (test zu kurz für 2 nicht überlappennde Fenster)
    cutover_dates: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "validation": {
                "CO1": "2014-07-31",  # Spätsommer
                "CO2": "2015-02-12",  # Winterende
                "CO3": "2015-05-24",  # Frühsommer
                "CO4": "2015-09-26",  # Herbstbeginn
                "CO5": "2016-01-12",  # Winteranfang
            },
            "test": {
                "CO6": "2016-12-02",  # Winteranfang
                "CO7": "2017-02-20",  # Winterende
            },
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
    strong_scale_factor_down: float = 0.7
    strong_peak_extra_w: float = 1000.0

    # mehr als stuck_value_min_hours (6 h), sonst markiert die Plausibilitätsprüfung nichts
    stuck_hours: int = 12

    def cutover_date(self, cutover_id: str) -> str:
        return self.cutover_dates[self.split][cutover_id]


STANDARD_CONFIG = StandardScenarioConfig()


# Szenario-Art -> erwartete Klasse, vor den Läufen festgelegt. absence (G2) kommt aus E2.
# Langsame Rampen sind nach der Definition kein Ereignis, still aufgenommen ist richtig, ein Reset ein Fehler
GOLDSTANDARD_EXPECTED: dict[str, str] = {
    "control": "normal",
    "scaled": "new_pattern",
    "scaled_strong": "new_pattern",
    "scaled_down": "new_pattern",
    "scaled_down_strong": "new_pattern",
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

# Sollverhalten bei der erwarteten Klasse
EXPECTED_DETECTION: dict[str, str] = {
    "new_pattern": "reset",
    "peak": "alarm",
    "normal": "silent",
    "measurement_error": "flag",
}
