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


# Standard-Szenarien der Komponentenstudien K2, K3 (Ebene 2) und K4. Experimente laufen nicht auf diesen Cutovern, weil K2 und K3 darauf eingestellt wurden
@dataclass(frozen=True)
class StandardScenarioConfig:
    # lokale Kalendertage im Train-Split, 120 Tage auseinander: Überwachung und Zeit danach (je 60 Tage) überlappen sich zwischen den Fenstern nicht
    cutover_dates: tuple[str, ...] = (
        "2013-10-15",
        "2014-02-12",
        "2014-06-12",
        "2014-10-10",
        "2015-02-07",
    )

    # Historie beginnt Kaltstart + diese Tage vor dem Cutover
    monitoring_before_cutover_days: int = 60
    margin_after_days: int = 60

    # Standard-Stufe "step", weitere Stärken über den Namen (step_30 = +30 W)
    step_injection_w: float = 100.0

    # alles ab Cutover um 30 % höher, im Mittel nach den Cutovern etwa ebenfalls +100 W.
    # Additiv gegen multiplikativ, der Stufen-Regressor in K4 lernt wegen log_transform einen Faktor.
    # Zugleich Endniveau der Rampen (ramp_28 = in 28 Tagen auf diesen Faktor)
    scale_factor: float = 1.3

    # peak: einmalige Zusatzlast am Cutover-Tag ab 17 Uhr, über 3 Stunden im Tagesmittel etwa +125 W (in Haus 1 alle 3 Wochen normal),
    # weitere Dauern über den Namen (peak_6 = 6 Stunden, Tagesmittel +250 W, über dem 99-%-Quantil echter Tage)
    peak_extra_w: float = 1000.0
    peak_start_hour: int = 17
    peak_hours: int = 3


STANDARD_CONFIG = StandardScenarioConfig()

# Beschriftung der Standard-Szenarien in den Reports, Stärken aus der Config bzw. aus dem Namen
KIND_LABELS: dict[str, str] = {
    "control": "keine Änderung",
    "step_30": "Dauerlast +30 W",
    "step_50": "Dauerlast +50 W",
    "step": f"Dauerlast +{STANDARD_CONFIG.step_injection_w:g} W",
    "step_200": "Dauerlast +200 W",
    "scaled": f"proportional ×{STANDARD_CONFIG.scale_factor:g}".replace(".", ","),
    "ramp_28": f"Rampe über 28 Tage auf ×{STANDARD_CONFIG.scale_factor:g}".replace(
        ".", ","
    ),
    "ramp_56": f"Rampe über 56 Tage auf ×{STANDARD_CONFIG.scale_factor:g}".replace(
        ".", ","
    ),
    "peak": f"Einzeltag-Spitze +{STANDARD_CONFIG.peak_extra_w:g} W über {STANDARD_CONFIG.peak_hours} h",
    "peak_6": f"Einzeltag-Spitze +{STANDARD_CONFIG.peak_extra_w:g} W über 6 h",
    "level_250": "ganzer Einzeltag +250 W",
}

# Szenario-Art (ohne Stärke) -> erwartete Klasse, vor den Läufen festgelegt. absence (G2) kommt aus E2, measurement_error (G5) nur aus E5.
# ramp (G4, nach E3 Teil B): öffnet eine Saisonverschiebung das Gate, ist new_pattern mit Reset richtig, still aufgenommen zählt wie control
GOLDSTANDARD_EXPECTED: dict[str, str] = {
    "control": "normal",
    "step": "new_pattern",
    "ramp": "new_pattern",
    "absence": "absence",
    "peak": "peak",
    "measurement_error": "measurement_error",
}
