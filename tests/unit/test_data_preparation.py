# python -m pytest tests/unit/test_data_preparation.py -v

from __future__ import annotations

from unittest.mock import Mock

import pandas as pd
import pytest

from src.data_preparation.selected_candidate_validation import build_selected_candidate_validation, select_candidate_role
from src.data_preparation.selected_data import build_selected_data


def test_build_selected_data_aligns_mains_on_utc_grid_without_filling() -> None:
    meter = Mock()
    meter.power_series_all_data.return_value = pd.Series(
        [10.0, None],
        index=pd.to_datetime(
            [
                "2020-01-01T00:00:06Z",
                "2020-01-01T00:00:12Z",
            ]
        ),
    )

    building = Mock()
    building.elec = {1: meter}

    dataset = Mock()
    dataset.buildings = {1: building}

    candidate_profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "mains_instance": 1,
                "longest_segment_start": "2020-01-01T00:00:01Z",
                "longest_segment_end": "2020-01-01T00:00:20Z",
            }
        ]
    )
    provisional_selection = pd.DataFrame(
        [
            {
                "selection_role": "primary",
                "candidate_id": "H1-M1",
            }
        ]
    )
    channel_registry = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "meter_type": "mains",
            }
        ]
    )

    aligned_data, manifest = build_selected_data(
        dataset=dataset,
        candidate_profiles=candidate_profiles,
        provisional_selection=provisional_selection,
        channel_registry=channel_registry,
        sample_period=6,
        canonical_ac_type="active",
        include_fallback=False,
    )

    frame = aligned_data["primary"]
    expected_index = pd.date_range(
        start="2020-01-01T00:00:06Z",
        end="2020-01-01T00:00:18Z",
        freq="6s",
    )

    assert frame.index.equals(expected_index)
    assert frame.index.name == "timestamp"
    assert frame.columns.tolist() == ["H1-M1"]
    assert frame.iloc[0, 0] == 10.0
    assert frame.iloc[1:, 0].isna().all()

    assert manifest.loc[0, "selection_role"] == "primary"
    assert manifest.loc[0, "candidate_id"] == "H1-M1"
    assert manifest.loc[0, "channel_role"] == "mains"
    assert manifest.loc[0, "meter_key"] == "H1-M1"


@pytest.mark.parametrize(
    ("include_fallback", "expected_roles"),
    [
        (False, ["primary"]),
        (True, ["primary", "fallback"]),
    ],
)
def test_build_selected_data_respects_include_fallback(
    include_fallback: bool,
    expected_roles: list[str],
) -> None:
    index = pd.to_datetime(
        [
            "2020-01-01T00:00:00Z",
            "2020-01-01T00:00:06Z",
        ]
    )

    primary_meter = Mock()
    primary_meter.power_series_all_data.return_value = pd.Series([10.0, 11.0], index=index)

    fallback_meter = Mock()
    fallback_meter.power_series_all_data.return_value = pd.Series([20.0, 21.0], index=index)

    primary_building = Mock()
    primary_building.elec = {1: primary_meter}

    fallback_building = Mock()
    fallback_building.elec = {1: fallback_meter}

    dataset = Mock()
    dataset.buildings = {
        1: primary_building,
        2: fallback_building,
    }

    candidate_profiles = pd.DataFrame(
        [
            {
                "candidate_id": "H1-M1",
                "house": 1,
                "mains_instance": 1,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-01-01T00:00:12Z",
            },
            {
                "candidate_id": "H2-M1",
                "house": 2,
                "mains_instance": 1,
                "longest_segment_start": "2020-01-01T00:00:00Z",
                "longest_segment_end": "2020-01-01T00:00:12Z",
            },
        ]
    )
    provisional_selection = pd.DataFrame(
        [
            {
                "selection_role": "primary",
                "candidate_id": "H1-M1",
            },
            {
                "selection_role": "fallback",
                "candidate_id": "H2-M1",
            },
        ]
    )
    channel_registry = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "meter_type": "mains",
            },
            {
                "house": 2,
                "meter_instance": 1,
                "meter_key": "H2-M1",
                "meter_type": "mains",
            },
        ]
    )

    aligned_data, manifest = build_selected_data(
        dataset=dataset,
        candidate_profiles=candidate_profiles,
        provisional_selection=provisional_selection,
        channel_registry=channel_registry,
        sample_period=6,
        canonical_ac_type="active",
        include_fallback=include_fallback,
    )

    assert list(aligned_data) == expected_roles
    assert manifest["selection_role"].tolist() == expected_roles


def test_candidate_validation_calculates_missingness_correctly() -> None:
    aligned_data = {
        "primary": pd.DataFrame(
            {
                "H1-M1": [10.0, None, None, 12.0],
            },
            index=pd.date_range(
                start="2020-01-01T00:00:00Z",
                periods=4,
                freq="1D",
            ),
        )
    }
    manifest = pd.DataFrame(
        [
            {
                "selection_role": "primary",
                "candidate_id": "H1-M1",
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "channel_role": "mains",
            }
        ]
    )

    channel_validation, candidate_validation = build_selected_candidate_validation(
        aligned_data=aligned_data,
        manifest=manifest,
        sample_period=86_400,
        min_mains_coverage_share=0.5,
        min_mains_valid_duration_days=2.0,
    )

    assert channel_validation.loc[0, "coverage_share"] == pytest.approx(0.5)
    assert channel_validation.loc[0, "missing_share"] == pytest.approx(0.5)
    assert channel_validation.loc[0, "longest_missing_run_seconds"] == 172_800

    assert bool(candidate_validation.loc[0, "grid_complete"])
    assert candidate_validation.loc[0, "mains_coverage_share"] == pytest.approx(0.5)
    assert candidate_validation.loc[0, "mains_valid_duration_days"] == pytest.approx(2.0)
    assert bool(candidate_validation.loc[0, "validation_passed"])
    assert candidate_validation.loc[0, "rejection_reason"] == ""


def test_candidate_validation_rejects_incomplete_grid() -> None:
    aligned_data = {
        "primary": pd.DataFrame(
            {
                "H1-M1": [10.0, 12.0],
            },
            index=pd.to_datetime(
                [
                    "2020-01-01T00:00:00Z",
                    "2020-01-03T00:00:00Z",
                ]
            ),
        )
    }
    manifest = pd.DataFrame(
        [
            {
                "selection_role": "primary",
                "candidate_id": "H1-M1",
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "channel_role": "mains",
            }
        ]
    )

    _, candidate_validation = build_selected_candidate_validation(
        aligned_data=aligned_data,
        manifest=manifest,
        sample_period=86_400,
        min_mains_coverage_share=1.0,
        min_mains_valid_duration_days=2.0,
    )

    assert not bool(candidate_validation.loc[0, "grid_complete"])
    assert not bool(candidate_validation.loc[0, "validation_passed"])
    assert candidate_validation.loc[0, "rejection_reason"] == "incomplete_grid"


@pytest.mark.parametrize(
    ("primary_passed", "fallback_passed", "expected_role"),
    [
        (True, True, "primary"),
        (False, True, "fallback"),
        (False, False, None),
    ],
)
def test_select_candidate_role_prefers_primary_then_fallback(
    primary_passed: bool,
    fallback_passed: bool,
    expected_role: str | None,
) -> None:
    candidate_validation = pd.DataFrame(
        [
            {
                "selection_role": "primary",
                "validation_passed": primary_passed,
            },
            {
                "selection_role": "fallback",
                "validation_passed": fallback_passed,
            },
        ]
    )

    assert select_candidate_role(candidate_validation) == expected_role