from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisConfig:
    # Einheit / AC-Type
    canonical_ac_type: str = "active"

    # House-/Window-Auswahl
    candidate_houses: tuple[int, ...] = (1, 2, 5)
    min_window_days: int = 84          # 12 Wochen
    preferred_window_days: int = 180   # ca. 6 Monate

    # Mains-Qualität
    min_mains_coverage_share: float = 0.95
    max_mains_missing_share: float = 0.05

    # Channel-Qualität auf Rohdatenebene
    min_duration_days: int = 84
    min_longest_good_section_days: int = 45
    min_sample_count: int = 100
    min_mean_power: float = 0.1
    max_zero_share: float = 0.95
    max_missing_share: float = 0.10
    max_longest_gap_seconds: int = 3600
    reject_negative_values: bool = True

    # Sample-Rate-Sanity
    expected_sample_period_seconds: int = 6
    max_median_sample_period_seconds: int = 12
    max_p99_sample_period_seconds: int = 60

    # 1h-Aggregation / späteres Prophet-Target
    target_freq: str = "1h"
    min_hour_coverage_share: float = 0.80
    preferred_hour_coverage_share: float = 0.90

    # Energy-Balance / Plausibilität
    max_energy_balance_deviation: float = 0.05
    max_unmetered_residual_share: float = 0.30

    # Appliance-Aktivität, später für Experiment-/Channel-Auswahl
    default_on_power_threshold_w: float = 10.0
    switch_threshold_w: float = 40.0
    min_activation_count: int = 30
    max_flatline_hours: int = 6

    # House-Level Gate
    min_usable_channels: int = 1
