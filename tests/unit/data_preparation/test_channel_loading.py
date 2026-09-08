# python -m pytest tests/unit/data_preparation/test_channel_loading.py -v

from __future__ import annotations

from unittest.mock import Mock

import pandas as pd

from src.data_preparation.aggregation.channel_loading import build_loaded_channels


def _quality_row(
    house: int, 
    meter_instance: int, 
    meter_key: str, 
    is_mains: bool, 
    start, 
    end
) -> dict:
    
    return {
        "house": house,
        "meter_instance": meter_instance,
        "meter_key": meter_key,
        "is_mains": is_mains,
        "start": start,
        "end": end,
    }


def _dataset(
    meters: dict[tuple[int, int], Mock]
) -> Mock:
    buildings: dict[int, Mock] = {}

    for (house, instance), meter in meters.items():
        building = buildings.setdefault(house, Mock())
        if not isinstance(building.elec, dict):
            building.elec = {}
        building.elec[instance] = meter

    dataset = Mock()
    dataset.buildings = buildings
    return dataset


def test_filters_by_selected_house_ids_and_mains_only() -> None:
    channel_quality = pd.DataFrame(
        [
            _quality_row(1, 1, "H1-M1", is_mains=True, start="2020-01-01", end="2020-01-02"),
            _quality_row(1, 2, "H1-M2", is_mains=False, start="2020-01-01", end="2020-01-02"),
            _quality_row(2, 1, "H2-M1", is_mains=True, start="2020-01-01", end="2020-01-02"),
        ]
    )
    mains_meter = Mock()
    mains_meter.power_series_all_data.return_value = pd.Series(
        [1.0], index=pd.to_datetime(["2020-01-01T00:00:00Z"])
    )
    dataset = _dataset({(1, 1): mains_meter})

    result = build_loaded_channels(
        dataset=dataset,
        channel_quality=channel_quality,
        canonical_ac_type="active",
        mains_only=True,
        selected_house_ids=[1],
    )

    assert list(result.keys()) == ["H1-M1"]


def test_rows_without_start_or_end_are_dropped() -> None:
    channel_quality = pd.DataFrame(
        [
            _quality_row(1, 1, "H1-M1", is_mains=True, start=pd.NaT, end="2020-01-02"),
        ]
    )
    dataset = _dataset({})

    result = build_loaded_channels(
        dataset=dataset,
        channel_quality=channel_quality,
        canonical_ac_type="active",
        mains_only=True,
    )

    assert result == {}


def test_missing_power_series_becomes_empty_utc_series() -> None:
    channel_quality = pd.DataFrame(
        [_quality_row(1, 1, "H1-M1", is_mains=True, start="2020-01-01", end="2020-01-02")]
    )
    meter = Mock()
    meter.power_series_all_data.return_value = None
    dataset = _dataset({(1, 1): meter})

    result = build_loaded_channels(
        dataset=dataset,
        channel_quality=channel_quality,
        canonical_ac_type="active",
        mains_only=True,
    )

    series = result["H1-M1"]
    assert series.empty
    assert series.dtype == "float64"
    assert isinstance(series.index, pd.DatetimeIndex)
    assert str(series.index.tz) == "UTC"
