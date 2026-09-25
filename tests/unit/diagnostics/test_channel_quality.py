# python -m pytest tests/unit/diagnostics/test_channel_quality.py -v

from __future__ import annotations

from unittest.mock import Mock

import pandas as pd
import pytest

from src.diagnostics.channel_quality import (
    CHANNEL_QUALITY_COLUMNS,
    build_channel_quality,
)


def _meter_with_series(series: pd.Series) -> Mock:
    meter = Mock()
    meter.load.return_value = iter([series.to_frame("power")])
    return meter


def _dataset_with_meters(meters: dict[tuple[int, int], Mock]) -> Mock:
    buildings: dict[int, Mock] = {}

    for (house, instance), meter in meters.items():
        building = buildings.setdefault(house, Mock())
        if not isinstance(building.elec, dict):
            building.elec = {}
        building.elec[instance] = meter

    dataset = Mock()
    dataset.buildings = buildings

    return dataset


def _registry_row(
    house: int,
    meter_instance: int,
    meter_type: str,
    has_canonical_ac_type: bool,
    sample_period_seconds: float = 6.0,
) -> dict:
    return {
        "house": house,
        "meter_instance": meter_instance,
        "meter_key": f"H{house}-M{meter_instance}",
        "meter_type": meter_type,
        "has_canonical_ac_type": has_canonical_ac_type,
        "sample_period_seconds": sample_period_seconds,
    }


def test_house_without_any_mains_row_is_excluded_entirely() -> None:
    channel_registry = pd.DataFrame(
        [_registry_row(1, 2, "submeter", has_canonical_ac_type=True)]
    )
    dataset = _dataset_with_meters({})

    result = build_channel_quality(
        dataset=dataset,
        channel_registry=channel_registry,
        canonical_ac_type="active",
        chunksize=None,
    )

    assert result.empty
    assert list(result.columns) == CHANNEL_QUALITY_COLUMNS


def test_house_with_non_canonical_mains_is_excluded_entirely() -> None:
    # mains reports only "apparent" power (has_canonical_ac_type=False) -> whole house drops out, even though its submeter does have canonical ac_type
    channel_registry = pd.DataFrame(
        [
            _registry_row(1, 1, "mains", has_canonical_ac_type=False),
            _registry_row(1, 2, "submeter", has_canonical_ac_type=True),
        ]
    )
    dataset = _dataset_with_meters({})

    result = build_channel_quality(
        dataset=dataset,
        channel_registry=channel_registry,
        canonical_ac_type="active",
        chunksize=None,
    )

    assert result.empty


def test_house_with_canonical_mains_keeps_mains_and_canonical_submeters() -> None:
    channel_registry = pd.DataFrame(
        [
            _registry_row(1, 1, "mains", has_canonical_ac_type=True),
            _registry_row(1, 2, "submeter", has_canonical_ac_type=True),
            _registry_row(1, 3, "submeter", has_canonical_ac_type=False),
        ]
    )

    index = pd.to_datetime(["2020-01-01T00:00:00Z", "2020-01-01T00:00:06Z"])
    mains_meter = _meter_with_series(pd.Series([10.0, 11.0], index=index))
    sub_meter = _meter_with_series(pd.Series([1.0, 2.0], index=index))

    dataset = _dataset_with_meters({(1, 1): mains_meter, (1, 2): sub_meter})

    result = build_channel_quality(
        dataset=dataset,
        channel_registry=channel_registry,
        canonical_ac_type="active",
        chunksize=None,
    )

    assert sorted(result["meter_instance"].tolist()) == [1, 2]


def test_profile_computes_sampling_share_and_dropout_rate() -> None:
    channel_registry = pd.DataFrame(
        [
            _registry_row(
                1, 1, "mains", has_canonical_ac_type=True, sample_period_seconds=6.0
            )
        ]
    )

    index = pd.to_datetime(
        [
            "2020-01-01T00:00:00Z",
            "2020-01-01T00:00:06Z",
            "2020-01-01T00:00:12Z",
            "2020-01-01T00:00:18Z",
            "2020-01-01T00:00:24Z",
        ]
    )
    series = pd.Series([10.0, None, 12.0, None, 14.0], index=index)
    dataset = _dataset_with_meters({(1, 1): _meter_with_series(series)})

    result = build_channel_quality(
        dataset=dataset,
        channel_registry=channel_registry,
        canonical_ac_type="active",
        chunksize=None,
    )

    row = result.iloc[0]

    assert row["start"] == index[0]
    assert row["end"] == index[-1]
    assert row["valid_sample_count"] == 3
    assert row["sampling_share"] == pytest.approx(3 / 5)
    assert row["dropout_rate"] == pytest.approx(2 / 5)
    assert row["quality_error"] is None


def test_channel_profiling_failure_is_captured_as_quality_error() -> None:
    channel_registry = pd.DataFrame(
        [_registry_row(1, 1, "mains", has_canonical_ac_type=True)]
    )
    dataset = Mock()
    dataset.buildings = {}

    result = build_channel_quality(
        dataset=dataset,
        channel_registry=channel_registry,
        canonical_ac_type="active",
        chunksize=None,
    )

    assert len(result) == 1
    assert result.loc[0, "quality_error"] is not None
    assert pd.isna(result.loc[0, "start"])


def test_missing_registry_column_raises() -> None:
    channel_registry = pd.DataFrame(
        [
            {
                "house": 1,
                "meter_instance": 1,
                "meter_key": "H1-M1",
                "has_canonical_ac_type": True,
                "sample_period_seconds": 6.0,
            }
        ]
    )

    with pytest.raises(ValueError, match="meter_type"):
        build_channel_quality(
            dataset=Mock(),
            channel_registry=channel_registry,
            canonical_ac_type="active",
            chunksize=None,
        )
