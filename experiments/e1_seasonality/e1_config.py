from dataclasses import dataclass, field

from experiments.common.standard_config import REFERENCE_SYSTEM

RUN_PREFIX = "e1"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e1_results"


BOTH_DIRECTIONS = (
    "control",
    "scaled",
    "scaled_down",
    "peak",
    "ramp_28",
    "ramp_56",
    "ramp_28_down",
    "ramp_56_down",
)

# Kennwert, an dem der Vorfilter ein Ereignis meldet (E1)
DETECTION_SIGNAL: dict[str, str] = {
    "peak": "alarm",
    "scaled": "sustained_drift",
    "scaled_down": "sustained_drift",
    "ramp_28": "sustained_drift",
    "ramp_28_down": "sustained_drift",
    "ramp_56": "sustained_drift",
    "ramp_56_down": "sustained_drift",
}


@dataclass(frozen=True)
class E1Config:
    kinds_by_cutover: dict[str, dict[str, tuple[str, ...]]] = field(
        default_factory=lambda: {
            "validation": {
                "CO1": BOTH_DIRECTIONS,
                "CO2": BOTH_DIRECTIONS,
                "CO3": BOTH_DIRECTIONS,
                "CO4": BOTH_DIRECTIONS,
                "CO5": BOTH_DIRECTIONS,
            },
            "test": {
                "CO6": ("control", "scaled", "peak", "ramp_28", "ramp_56"),
                "CO7": (
                    "control",
                    "scaled_down",
                    "peak",
                    "ramp_28_down",
                    "ramp_56_down",
                ),
            },
        }
    )
    # ohne Adaption und ohne LLM, die Reihen laufen nach dem Ereignis nicht auseinander
    system: str = REFERENCE_SYSTEM
