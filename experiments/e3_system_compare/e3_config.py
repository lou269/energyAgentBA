from __future__ import annotations

from dataclasses import dataclass, field

from experiments.common.standard_config import LLM_SYSTEM, REFERENCE_SYSTEM, RULE_SYSTEM

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
            "test": ("CO6", "CO7"),
        }
    )

    reference_system: str = REFERENCE_SYSTEM
    rule_system: str = RULE_SYSTEM
    llm_system: str = LLM_SYSTEM

    week_days: int = 7

    event_series: dict[str, tuple[tuple[int, str], ...]] = field(
        default_factory=lambda: {
            "single_days": ((0, "peak_strong"), (10, "peak_strong"), (17, "stuck")),
            "scaled": ((0, "scaled_strong"),),
        }
    )
