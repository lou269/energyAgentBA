from dataclasses import dataclass, field

from experiments.common.standard_config import REFERENCE_SYSTEM

RUN_PREFIX = "e1"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e1_results"


@dataclass(frozen=True)
class E1Config:
    # keine Cutover, vor denen die Regel im Kontrolllauf zurücksetzt
    # Sprünge nur mit der Saison: nach unten an CO3 (Niveau fällt um 19 %), an CO4 beide Richtungen, nach oben an CO5
    kinds_by_cutover: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "CO3": ("control", "scaled_down", "peak", "ramp_28_down", "ramp_56_down"),
            "CO4": (
                "control",
                "scaled",
                "scaled_down",
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
