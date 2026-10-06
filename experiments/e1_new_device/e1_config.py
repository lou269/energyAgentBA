from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from experiments.common.standard_config import (
    LLM_SYSTEM,
    REFERENCE_SYSTEM,
    RULE_SYSTEM,
    STANDARD_CONFIG,
)

RUN_PREFIX = "e1"
RESULTS_FILE = "e1_results"
DEVICE_WINDOWS_FILE = "e1_device_windows"
DEVICES_HOURLY_FILE = "e1_devices_hourly"


@dataclass(frozen=True)
class E1Config:
    cutover_ids: tuple[str, ...] = ("CO3", "CO4", "CO5")
    # Art -> Gerätekanäle, die bis zum Cutover herausgerechnet werden

    devices: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {"washer_dryer": ("H1_M5",)}
    )
    # ein neues Gerät ist eine dauerhafte Änderung
    target_classification: str = "new_pattern"

    reference_system: str = REFERENCE_SYSTEM
    rule_system: str = RULE_SYSTEM
    llm_system: str = LLM_SYSTEM

    @property
    def device_selection_subdir(self) -> Path:
        return Path("device_selection") / STANDARD_CONFIG.split
