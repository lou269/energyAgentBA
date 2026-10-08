from dataclasses import dataclass, field

from experiments.common.standard_config import REFERENCE_SYSTEM

RUN_PREFIX = "e1"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e1_results"


@dataclass(frozen=True)
class E1Config:
    # keine Cutover, vor denen die Regel im Kontrolllauf zurücksetzt
    # scaled nicht an CO3, dort fällt das echte Niveau um 19 %
    kinds_by_cutover: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "CO3": ("control", "peak", "ramp_28_down", "ramp_56_down"),
            "CO4": (
                "control",
                "scaled",
                "peak",
                "ramp_28",
                "ramp_56",
                "ramp_28_down",
                "ramp_56_down",
            ),
            "CO5": ("control", "scaled", "peak", "ramp_28", "ramp_56"),
        }
    )
    # ohne Adaption und ohne LLM, die Reihen laufen nach dem Ereignis nicht auseinander
    system: str = REFERENCE_SYSTEM
