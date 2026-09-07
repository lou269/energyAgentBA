from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class AnalysisConfig:
    # Channel registry / gemeinsame Messgröße
    canonical_ac_type: str = "active"

    # Channel quality
    channel_quality_chunksize: int = 1_000_000

    # Auxiliary appliance selection
    min_auxiliary_window_coverage_share: float = 0.8

        