from __future__ import annotations

from dataclasses import dataclass

from src.config.config_forecasting import ForecastingConfig
from src.config.project_config import ProjectConfig

# für alle Studien gleich, wird deshalb nicht durch die Funktionen gereicht
PROJECT_CONFIG = ProjectConfig()
LOCAL_TIMEZONE = PROJECT_CONFIG.timezone
# Nachkommastellen in ergebnis.md und den Ergebnis-CSVs
DECIMALS = PROJECT_CONFIG.result_decimals
# Kaltstart des Online-Zyklus vor dem ersten Entscheidungstag
COLDSTART_DAYS = ForecastingConfig().cycle_coldstart_days

# Meldung = Tag, zu dem der Nutzer eine Erklärung bekäme (in SYS3 ein LLM-Aufruf)
NOTIFICATION_CLASSIFICATIONS: tuple[str, ...] = (
    "peak",
    "low",
    "new_pattern",
    "absence",
)
NOTIFICATION_PERIOD_DAYS = 30


# Standard-Szenarien, auf denen K3, K4 (Ebene 2), K5 und später E3/E5 laufen
@dataclass(frozen=True)
class StandardScenarioConfig:
    # lokale Kalendertage, je eine Jahreszeit, alle im Train-Split und ohne bekannte Kalenderereignisse im Fenster
    cutover_dates: tuple[str, ...] = (
        "2013-10-15",
        "2014-01-15",
        "2014-04-15",
        "2014-07-15",
    )

    # Historie beginnt Kaltstart + diese Tage vor dem Cutover
    monitoring_before_cutover_days: int = 60
    margin_after_days: int = 60

    step_injection_w: float = 100.0

    # alles ab Cutover um 30 % höher, im Mittel nach den Cutovern etwa ebenfalls +100 W.
    # Additiv gegen multiplikativ, der Stufen-Regressor in K5 lernt wegen log_transform einen Faktor
    scale_factor: float = 1.3


STANDARD_CONFIG = StandardScenarioConfig()
