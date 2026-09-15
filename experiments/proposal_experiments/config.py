from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scenarios"


''' E1 - NEUES GERÄT '''
@dataclass(frozen=True)
class E1Config:
    device_meter_key: str = "H1_M5"  # washer dryer, siehe channel_registry.csv appliances
    coldstart_hours: int = 168

    cutover_time: str | None = "2014-04-15T00:00:00+00:00"

    # so viel Historie vor dem Cutover, dass long_term_window_hourly (720h=30 Tage) + Coldstart (168h) beim Cutover-Tag einen validen Referenzwert liefern
    margin_before_days: int = 45
    margin_after_days: int = 28


''' E2 - ABWESENHEIT '''
@dataclass(frozen=True)
class E2Config:
    calendar_events_file: Path = SCENARIOS_DIR / "calendar_events.json"

    active_absence_event_id: str = "vacation-2013-06"

    decision_time_margin_before_days: int = 7
    decision_time_margin_after_days: int = 4
    
    
    coldstart_hours: int = 168

    min_coverage_share_for_subtraction: float = 0.9
    
    
    