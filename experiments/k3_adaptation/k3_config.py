from dataclasses import dataclass
from typing import Literal

from experiments.common.standard_config import REFERENCE_SYSTEM, RULE_SYSTEM


RUN_PREFIX = "k3"
MASKING_RUN_PREFIX = "k3_mask"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "k3_results"
MASKING_RESULTS_FILE = "k3_mask_results"
MASKING_DECISIONS_FILE = "k3_mask_decisions"

K3Strategy = Literal["none", "cut", "step_regressor"]


# Cutover, Zeitfenster und Faktor kommen aus StandardScenarioConfig
@dataclass(frozen=True)
class K3Config:
    # Zyklus wie dieses System, die Adaptionen gibt das Orakel vor
    cycle_system: str = REFERENCE_SYSTEM

    # Standard-Cutover (Kennungen aus StandardScenarioConfig)
    cutovers: tuple[str, ...] = ("CO1", "CO2", "CO3", "CO4", "CO5")

    # 6 = frühestmögliches new_pattern (6 von 7 Tagen auffällig, ausgewertet um Mitternacht danach), 19 = späte Erkennung, etwa so spät setzt der Detektor bei scaled im Median zurück (K1-Diagnose)
    trigger_days: tuple[int, ...] = (6, 19)
    # Trainingsfenster minus Schnitt bei Trigger minus streak_tolerance_window_days: nach so vielen Tagen trainieren Aktion und keine Aktion auf denselben Tagen, die Differenz ist danach null
    evaluation_days = 23
    # Spalten der Ergebnisse: Mittel der Stundenfehler und Fehler des Tagesmittels, jeweils je Prognosetag
    error_metrics: tuple[str, ...] = ("mae_w", "day_error_w")
    # Tage seit Cutover, für die Prognose minus Messung (mit Vorzeichen) ohne Aktion ausgewertet wird, davor als Bezug
    bias_first_day: int = -3
    bias_last_day: int = 10

    kinds: tuple[str, ...] = ("scaled",)

    # none läuft einmal je Szenario ohne Trigger mit
    strategies: tuple[K3Strategy, ...] = ("cut", "step_regressor")

    # Kennzahlen zu diesem Ereignis
    key_figure_kind: str = "scaled"

    # Teil 2, peak/low ausblenden: decision_system zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach
    decision_system: str = RULE_SYSTEM
    masking_kinds: tuple[str, ...] = ("control", "scaled")
    masked_classifications: tuple[str, ...] = ("peak", "low")
    # in den ersten zwei Wochen nach dem Cutover kann der Beginn einer echten Änderung noch als peak ausgeblendet werden
    masking_early_days: int = 14
