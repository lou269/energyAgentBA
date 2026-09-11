from __future__ import annotations

from dataclasses import dataclass, field



@dataclass(frozen=True)
class DataPreparationConfig:
    selected_house_ids: list[int] = field(default_factory=lambda: [1])
    alignment_sample_period_seconds: int = 6
    canonical_ac_type: str = "active"
    
    min_coverage_share: float = 0.80

    max_availability_gap_hours: int = 6

    min_mains_coverage_share: float = 0.95
    min_mains_valid_duration_days: float = 45.0