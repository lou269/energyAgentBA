from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnalysisConfig:
    # Channel registry / gemeinsame Messgröße
    canonical_ac_type: str = "active"

    # Channel quality
    channel_quality_chunksize: int = 1_000_000

    # House eligibility
    min_valid_sample_count: int = 2

    # Provisional candidate selection
    min_longest_segment_days: float = 45.0

    # Auxiliary appliance selection
    min_auxiliary_window_coverage_share: float = 0.0

        