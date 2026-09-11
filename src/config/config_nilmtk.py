from __future__ import annotations

from dataclasses import dataclass, field

# von Analysis und Data Preparation geteilt, damit beide nie auf unterschiedliche Kanaltypen laufen
CANONICAL_AC_TYPE = "active"

''' ANALYSIS '''
@dataclass(frozen=True)
class AnalysisConfig:
    canonical_ac_type: str = CANONICAL_AC_TYPE

    # Channel quality
    channel_quality_chunksize: int = 1_000_000

    # Auxiliary appliance selection
    min_auxiliary_window_coverage_share: float = 0.8

''' DATA PREPARATION '''
@dataclass(frozen=True)
class DataPreparationConfig:
    selected_house_ids: list[int] = field(default_factory=lambda: [1])
    alignment_sample_period_seconds: int = 6
    canonical_ac_type: str = CANONICAL_AC_TYPE

    min_coverage_share: float = 0.80
    max_availability_gap_hours: int = 6

    min_mains_coverage_share: float = 0.95
    min_mains_valid_duration_days: float = 45.0
