from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from experiments.common.standard_config import (
    GOLDSTANDARD_EXPECTED,
    LLM_SYSTEM,
    REFERENCE_SYSTEM,
    RULE_SYSTEM,
)

RUN_PREFIX = "e1"
CONTROL_RUN_PREFIX = "e1_control"
# von e1_device_check geschrieben (nilmtk-env), von e1_scenarios gelesen
DEVICES_HOURLY_FILE = "e1_devices_hourly"


@dataclass(frozen=True)
class E1Config:
    split: str = "validation"

    reference_config: str = REFERENCE_SYSTEM
    target_classification: str = GOLDSTANDARD_EXPECTED["step"]
    systems: tuple[str, ...] = (REFERENCE_SYSTEM, RULE_SYSTEM, LLM_SYSTEM)

    # Waschtrockner, größter Anteil am Mains-Verbrauch (e1_device_check)
    device_meter_keys: tuple[str, ...] = ("H1_M5",)

    # lokales Datum, wird über local_midnight_utc() zur Mitternacht Ortszeit Cutover, nach dem H1_M5 den größten Anteil an Mains hat (e1_device_check)
    cutover_date: str = "2014-03-24"

    margin_before_days: int = 14
    # new_pattern braucht frühestens 6 Treffer im 7-Tage-Fenster, danach bleiben rund 3 Wochen, um die Adaption zu bewerten
    margin_after_days: int = 28

    # Cutover-Kandidaten alle 4 Wochen, damit jeder auf denselben Wochentag fällt
    cutover_step_days: int = 28
    min_device_coverage: float = 0.9

    @property
    def device_selection_subdir(self) -> Path:
        return Path("device_selection") / self.split
