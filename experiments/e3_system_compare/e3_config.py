from __future__ import annotations

from dataclasses import dataclass, field

from experiments.common.standard_config import LLM_SYSTEM, REFERENCE_SYSTEM

RUN_PREFIX = "e3"
# vom Runner geschrieben, vom Report gelesen
RESULTS_FILE = "e3_results"
# Ordner je Reihe und Cutover unter raw/, darüber ordnet die Evaluation Laufzeiten und LLM-Antworten zu
SCENARIO_DIRECTORY = "{series}_{cutover_date}"


@dataclass(frozen=True)
class E3Config:
    cutovers: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "validation": ("CO2", "CO3"),
            "test": ("CO6", "CO7", "CO8"),
        }
    )

    reference_system: str = REFERENCE_SYSTEM
    llm_system: str = LLM_SYSTEM

    week_days: int = 7

    event_series: dict[str, tuple[tuple[int, str], ...]] = field(
        default_factory=lambda: {
            "scaled": ((0, "scaled_strong"),),
            "scaled_down": ((0, "scaled_down_strong"),),
            "ramp_28": ((0, "ramp_28_strong"),),
            "ramp_28_down": ((0, "ramp_28_down_strong"),),
        }
    )
