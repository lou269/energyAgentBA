# python -m pytest tests/unit/test_analysis.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.analysis.diagnostics.house_eligibility import build_house_eligibility
from src.analysis.selection.auxiliary_appliance_selection import build_auxiliary_appliance_selection
from src.analysis.selection.candidate_profiling import build_candidate_profiles
from src.analysis.selection.provisional_selection import build_candidate_selection_outputs


def test_house_without_canonical_mains_is_excluded() -> None:
    channel_registry = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "meter_type": "mains",
                "has_canonical_ac_type": False,
            }
        ]
    )
    channel_quality = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "valid_sample_count": 100,
                "good_section_count": 1,
                "quality_error": None,
            }
        ]
    )

    result = build_house_eligibility(
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        min_valid_sample_count=2,
    )

    assert not bool(result.loc[0, "eligible_for_candidate_profiling"])
    assert result.loc[0, "exclusion_reason"] == "no_canonical_mains"


def test_house_with_insufficient_mains_quality_is_excluded() -> None:
    channel_registry = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "meter_type": "mains",
                "has_canonical_ac_type": True,
            }
        ]
    )
    channel_quality = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "valid_sample_count": 1,
                "good_section_count": 1,
                "quality_error": None,
            }
        ]
    )

    result = build_house_eligibility(
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        min_valid_sample_count=2,
    )

    assert not bool(result.loc[0, "eligible_for_candidate_profiling"])
    assert result.loc[0, "exclusion_reason"] == "mains_quality_insufficient"


def test_candidate_profile_uses_longest_good_section() -> None:
    channel_registry = pd.DataFrame(
        [{"house": 1, "meter_instance": 1, "meter_key": "H1-M1", "meter_type": "mains"}]
    )
    channel_quality = pd.DataFrame(
        [{"house": 1, "meter_instance": 1, "meter_key": "H1-M1", "sampling_share": 0.9}]
    )
    house_eligibility = pd.DataFrame(
        [{"house": 1, "mains_instance": 1, "eligible_for_candidate_profiling": True}]
    )
    good_sections = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "start": "2020-01-01T00:00:00Z",
                "end": "2020-01-11T00:00:00Z",
            },
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "start": "2020-02-01T00:00:00Z",
                "end": "2020-03-17T00:00:00Z",
            },
        ]
    )

    result = build_candidate_profiles(
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        house_eligibility=house_eligibility,
        good_sections=good_sections,
    )

    assert result.loc[0, "candidate_id"] == "H1-M1"
    assert result.loc[0, "segment_count"] == 2
    assert result.loc[0, "longest_segment_days"] == pytest.approx(45.0)
    assert result.loc[0, "longest_segment_start"] == pd.Timestamp("2020-02-01T00:00:00Z")
    assert result.loc[0, "longest_segment_end"] == pd.Timestamp("2020-03-17T00:00:00Z")


def test_candidate_at_45_day_boundary_is_eligible() -> None:
    profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "longest_segment_days": 45.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-02-15T00:00:00Z",
                "total_coverage_days": 45.0,
                "sampling_share": 0.9,
            },
            {
                "candidate_id": "H2-M1",
                "house": 2,
                "longest_segment_days": 44.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-02-14T00:00:00Z",
                "total_coverage_days": 44.0,
                "sampling_share": 0.9,
            },
        ]
    )

    selection, decisions = build_candidate_selection_outputs(
        candidate_profiles=profiles, min_longest_segment_days=45.0
    )

    assert selection.to_dict("records") == [
        {"selection_role": "primary", "candidate_id": "H1-M1"}
    ]

    decisions = decisions.set_index("candidate_id")

    assert bool(decisions.loc["H1-M1", "eligible_for_selection"])
    assert not bool(decisions.loc["H2-M1", "eligible_for_selection"])
    assert decisions.loc["H2-M1", "decision_reason"] == "longest_segment_below_threshold"


def test_candidate_ranking_is_deterministic() -> None:
    profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H2-M1",
                "house": 2,
                "longest_segment_days": 60.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-03-01T00:00:00Z",
                "total_coverage_days": 60.0,
                "sampling_share": 0.9,
            },
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "longest_segment_days": 60.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-03-01T00:00:00Z",
                "total_coverage_days": 60.0,
                "sampling_share": 0.9,
            },
        ]
    )

    selection, decisions = build_candidate_selection_outputs(
        candidate_profiles=profiles, min_longest_segment_days=45.0
    )

    assert selection.to_dict("records") == [
        {"selection_role": "primary", "candidate_id": "H1-M1"},
        {"selection_role": "fallback", "candidate_id": "H2-M1"},
    ]
    
    assert decisions["candidate_id"].tolist() == ["H1-M1", "H2-M1"]
    assert decisions["selection_rank"].tolist() == [1, 2]


def test_fallback_is_selected_from_different_house() -> None:
    profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "longest_segment_days": 60.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-03-01T00:00:00Z",
                "total_coverage_days": 60.0,
                "sampling_share": 0.9,
            },
            {
                "candidate_id": "H1-M2",
                "house": 1,
                "longest_segment_days": 59.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-02-29T00:00:00Z",
                "total_coverage_days": 59.0,
                "sampling_share": 0.9,
            },
            {
                "candidate_id": "H2-M1",
                "house": 2,
                "longest_segment_days": 58.0,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-02-28T00:00:00Z",
                "total_coverage_days": 58.0,
                "sampling_share": 0.9,
            },
        ]
    )

    selection, decisions = build_candidate_selection_outputs(
        candidate_profiles=profiles, min_longest_segment_days=45.0
    )

    assert selection.to_dict("records") == [
        {"selection_role": "primary", "candidate_id": "H1-M1"},
        {"selection_role": "fallback", "candidate_id": "H2-M1"},
    ]

    decisions = decisions.set_index("candidate_id")

    assert decisions.loc["H1-M2", "selection_role"] == "not_selected"
    assert decisions.loc["H1-M2", "decision_reason"] == "same_house_as_primary"
    assert decisions.loc["H2-M1", "decision_reason"] == "highest_ranked_candidate_from_different_house"


def _base_auxiliary_registry_row(meter_instance: int, meter_key: str, appliance: str) -> dict:
    return {
        "house": 1,
        "meter_instance": meter_instance,
        "meter_key": meter_key,
        "meter_type": "submeter",
        "appliances": appliance,
        "has_canonical_ac_type": True,
    }


def test_auxiliary_selection_ranks_by_window_coverage_and_excludes_unusable_channels() -> None:
    candidate_profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-01-31T00:00:00Z",
            }
        ]
    )
    provisional_selection = pd.DataFrame(
        [{"selection_role": "primary", "candidate_id": "H1-M1"}]
    )
    channel_registry = pd.DataFrame(
        [
            _base_auxiliary_registry_row(2, "H1-M2", "kettle"),
            _base_auxiliary_registry_row(3, "H1-M3", "fridge"),
            {**_base_auxiliary_registry_row(4, "H1-M4", "toaster"), "has_canonical_ac_type": False},
            _base_auxiliary_registry_row(5, "H1-M5", "microwave"),
            _base_auxiliary_registry_row(6, "H1-M6", ""),
        ]
    )
    channel_quality = pd.DataFrame(
        [
            {
                "house": 1, "meter_instance": 2, "meter_key": "H1-M2",
                "sampling_share": 0.95, "good_section_coverage_share": 0.8,
                "longest_good_section_days": 10.0, "quality_error": None,
            },
            {
                "house": 1, "meter_instance": 3, "meter_key": "H1-M3",
                "sampling_share": 0.90, "good_section_coverage_share": 0.7,
                "longest_good_section_days": 20.0, "quality_error": None,
            },
            {
                "house": 1, "meter_instance": 5, "meter_key": "H1-M5",
                "sampling_share": 0.99, "good_section_coverage_share": 0.99,
                "longest_good_section_days": 99.0, "quality_error": "profiling failed",
            },
        ]
    )
    good_sections = pd.DataFrame(
        [
            {
                "house": 1, "meter_instance": 2, "meter_key": "H1-M2",
                "start": "2020-01-10T00:00:00Z", "end": "2020-01-25T00:00:00Z",
            },
            {
                "house": 1, "meter_instance": 3, "meter_key": "H1-M3",
                "start": "2020-01-05T00:00:00Z", "end": "2020-01-30T00:00:00Z",
            },
        ]
    )

    result = build_auxiliary_appliance_selection(
        candidate_profiles=candidate_profiles,
        provisional_selection=provisional_selection,
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        good_sections=good_sections,
    )

    assert result["meter_instance"].tolist() == [3, 2]
    assert result["availability_rank"].tolist() == [1, 2]
    assert result["selected_window_coverage_share"].tolist() == pytest.approx([25 / 30, 15 / 30])
    assert result.loc[0, "longest_selected_window_overlap_days"] == pytest.approx(25.0)

    # non-canonical (M4), quality_error (M5) and no-appliance-name (M6) channels must never show up as auxiliary candidates
    assert set(result["meter_instance"]) == {2, 3}


def test_auxiliary_selection_tiebreaks_equal_ranking_by_meter_instance() -> None:
    candidate_profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-01-31T00:00:00Z",
            }
        ]
    )
    provisional_selection = pd.DataFrame(
        [{"selection_role": "primary", "candidate_id": "H1-M1"}]
    )
    channel_registry = pd.DataFrame(
        [
            _base_auxiliary_registry_row(10, "H1-M10", "kettle"),
            _base_auxiliary_registry_row(5, "H1-M5", "fridge"),
        ]
    )
    channel_quality = pd.DataFrame(
        [
            {
                "house": 1, "meter_instance": instance, "meter_key": key,
                "sampling_share": 0.9, "good_section_coverage_share": 1.0,
                "longest_good_section_days": 30.0, "quality_error": None,
            }
            for instance, key in [(10, "H1-M10"), (5, "H1-M5")]
        ]
    )
    good_sections = pd.DataFrame(
        [
            {
                "house": 1, "meter_instance": instance, "meter_key": key,
                "start": "2020-01-01T00:00:00Z", "end": "2020-01-31T00:00:00Z",
            }
            for instance, key in [(10, "H1-M10"), (5, "H1-M5")]
        ]
    )

    result = build_auxiliary_appliance_selection(
        candidate_profiles=candidate_profiles,
        provisional_selection=provisional_selection,
        channel_registry=channel_registry,
        channel_quality=channel_quality,
        good_sections=good_sections,
    )

    assert result["meter_instance"].tolist() == [5, 10]
    assert result["availability_rank"].tolist() == [1, 2]
