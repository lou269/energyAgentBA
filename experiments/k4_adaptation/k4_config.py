from dataclasses import dataclass
from typing import Literal


RUN_PREFIX = "k4"
MASKING_RUN_PREFIX = "k4_mask"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "k4_results"
MASKING_RESULTS_FILE = "k4_mask_results"
MASKING_DECISIONS_FILE = "k4_mask_decisions"

K4Strategy = Literal["none", "cut", "step_regressor"]


# Cutover, Zeitfenster, Stufe und Faktor kommen aus StandardScenarioConfig, damit K2 und K4 auf denselben Szenarien laufen
@dataclass(frozen=True)
class K4Config:
    # Zyklus wie dieses System, die Adaptionen gibt das Orakel vor
    cycle_system: str = "SYS1"

    # 6 = frühestmögliches new_pattern (6 von 7 Tagen auffällig, ausgewertet um Mitternacht danach), 19 = späte Erkennung, so spät erkennt der Detektor +100 W im Mittel in K2
    trigger_days: tuple[int, ...] = (6, 19)
    evaluation_days: int = 30

    # scaled ist das zweite Ereignis neben der Dauerlast: additiv gegen multiplikativ
    kinds: tuple[str, ...] = ("control", "step", "scaled")

    # none läuft einmal je Szenario ohne Trigger mit
    strategies: tuple[K4Strategy, ...] = ("cut", "step_regressor")

    # Kennzahlen zu diesem Ereignis, der Mehrfehler ohne Aktion zusätzlich in dieser Woche
    key_figure_kind: str = "step"
    key_figure_late_week: int = 2

    # Teil 2, peak/low ausblenden: decision_system zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach
    decision_system: str = "SYS2"
    masking_kinds: tuple[str, ...] = ("control", "step")
    masked_classifications: tuple[str, ...] = ("peak", "low")
    # in den ersten zwei Wochen nach dem Cutover kann der Beginn einer echten Änderung noch als peak ausgeblendet werden
    masking_early_days: int = 14
