from __future__ import annotations

from dataclasses import dataclass



@dataclass(frozen=True)
class DataPreparationConfig:
    # Selected data / temporal alignment
    alignment_sample_period_seconds: int = 6
    canonical_ac_type: str = "active"
    include_fallback: bool = True
    selected_data_chunksize: int = 1_000_000

    # Selected candidate validation
    min_mains_coverage_share: float = 0.95
    min_mains_valid_duration_days: float = 45.0
    