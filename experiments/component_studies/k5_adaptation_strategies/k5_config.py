from dataclasses import dataclass
from typing import Literal

from src.config.config_forecasting import SYS_VARIANTS


K5Strategy = Literal["none", "cut", "step_regressor"]


# Cutover, Zeitfenster und Stufe kommen aus K3Config, damit beide Studien auf denselben Szenarien laufen
@dataclass(frozen=True)
class K5Config:
    # 6 = frühestmögliches new_pattern (6 von 7 Tagen auffällig, ausgewertet um Mitternacht danach), 12 = späte Erkennung wie live im April in K3
    trigger_days: tuple[int, ...] = (6, 12)
    evaluation_days: int = 30

    # zweites Ereignis neben der +100-W-Dauerlast aus K3: alles um 30 % höher, im Mittel nach den Cutovern etwa ebenfalls +100 W.
    # Additiv gegen multiplikativ, der Regressor lernt wegen log_transform einen Faktor
    scale_factor: float = 1.3

    # none läuft einmal je Szenario ohne Trigger mit
    strategies: tuple[K5Strategy, ...] = ("cut", "step_regressor")


K5_CYCLE_CONFIG = SYS_VARIANTS["SYS1"]

# Teil 2, peak/low ausblenden: SYS2 zeichnet die Entscheidungen auf, das Orakel spielt sie ohne und mit Ausblenden nach
K5_DECISION_CONFIG = SYS_VARIANTS["SYS2"]
K5_MASKED_CLASSIFICATIONS: tuple[str, ...] = ("peak", "low")
K5_MASKING_VARIANTS: dict[str, tuple[str, ...]] = {"replay": (), "mask": K5_MASKED_CLASSIFICATIONS}
# in den ersten zwei Wochen nach dem Cutover kann der Beginn einer echten Änderung noch als peak ausgeblendet werden
K5_MASKING_EARLY_DAYS = 14