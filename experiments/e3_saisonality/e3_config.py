from dataclasses import dataclass

from experiments.common.standard_config import RULE_SYSTEM

RUN_PREFIX = "e3"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e3_results"


@dataclass(frozen=True)
class E3Config:
    # abrupte Stufe und Rampen auf dasselbe Niveau (scale_factor), das System wie im Betrieb, nur Regel statt LLM.
    # Rampen höchstens so lang wie margin_after_days der Standard-Szenarien (60), sonst endet der Lauf mitten im Anstieg
    kinds: tuple[str, ...] = ("control", "scaled", "ramp_28", "ramp_56")
    system_id: str = RULE_SYSTEM
    # Standard-Cutover (Kennungen aus StandardScenarioConfig)
    cutovers: tuple[str, ...] = ("CO1", "CO2", "CO3", "CO4", "CO5")
