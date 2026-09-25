from dataclasses import dataclass
from typing import Literal

from experiments.common.evaluation import ALL_DAYS


RUN_PREFIX = "k5"
MASKING_RUN_PREFIX = "k5_mask"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "k5_results"
MASKING_RESULTS_FILE = "k5_mask_results"
MASKING_DECISIONS_FILE = "k5_mask_decisions"

K5Strategy = Literal["none", "cut", "step_regressor"]


# Cutover, Zeitfenster, Stufe und Faktor kommen aus StandardScenarioConfig, damit K3 und K5 auf denselben Szenarien laufen
@dataclass(frozen=True)
class K5Config:
    # Zyklus wie dieses System, die Adaptionen gibt das Orakel vor
    cycle_system: str = "SYS1"

    # 6 = frühestmögliches new_pattern (6 von 7 Tagen auffällig, ausgewertet um Mitternacht danach), 12 = späte Erkennung wie live im April in K3
    trigger_days: tuple[int, ...] = (6, 12)
    evaluation_days: int = 30

    # scaled ist das zweite Ereignis neben der Dauerlast: additiv gegen multiplikativ
    kinds: tuple[str, ...] = ("control", "step", "scaled")

    # none läuft einmal je Szenario ohne Trigger mit
    strategies: tuple[K5Strategy, ...] = ("cut", "step_regressor")

    # Kennzahlen zu diesem Ereignis, der Mehrfehler ohne Aktion zusätzlich in dieser Woche
    key_figure_kind: str = "step"
    key_figure_late_week: int = 2

    # Teil 2, peak/low ausblenden: decision_system zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach
    decision_system: str = "SYS2"
    masking_kinds: tuple[str, ...] = ("control", "step")
    masked_classifications: tuple[str, ...] = ("peak", "low")
    # in den ersten zwei Wochen nach dem Cutover kann der Beginn einer echten Änderung noch als peak ausgeblendet werden
    masking_early_days: int = 14


STRATEGY_LABELS: dict[str, str] = {
    "none": "keine Aktion",
    "cut": "cut, Historie ab t_c",
    "step_regressor": "Stufen-Regressor",
}
MASKING_PHASE_LABELS: dict[str, str] = {
    "before_cutover": "vor Cutover",
    "early": f"Tag 0-{K5Config.masking_early_days - 1}",
    "late": f"ab Tag {K5Config.masking_early_days}",
    ALL_DAYS: "alle Tage",
}
