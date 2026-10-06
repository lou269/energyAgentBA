from dataclasses import dataclass, field

from experiments.common.standard_config import (
    LLM_SYSTEM,
    REFERENCE_SYSTEM,
    RULE_SYSTEM,
)

RUN_PREFIX = "e3"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e3_results"


@dataclass(frozen=True)
class E3Config:
    # keine Cutover, vor denen die Regel im Kontrolllauf zurücksetzt
    kinds_by_cutover: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "CO3": ("control", "ramp_28_down", "ramp_56_down"),
            "CO4": ("control", "ramp_28", "ramp_56", "ramp_28_down", "ramp_56_down"),
            "CO5": ("control", "ramp_28", "ramp_56"),
        }
    )
    reference_system: str = REFERENCE_SYSTEM
    rule_system: str = RULE_SYSTEM
    llm_system: str = LLM_SYSTEM
