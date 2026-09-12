# python -m pytest tests/unit/data_preparation/test_auxiliary_appliance_selection.py -v

from __future__ import annotations

from unittest.mock import Mock

import pandas as pd
import pytest

from src.data_preparation.auxiliary_appliance_selection import filter_candidate_channels, rank_by_coverage

WINDOW_START = pd.Timestamp("2020-01-01", tz="UTC")
WINDOW_END = pd.Timestamp("2020-01-08", tz="UTC")


def _registry_row(
    meter_instance: int, 
    meter_key: str, 
    appliances: str
) -> dict:
    return {
        "house": 1,
        "meter_instance": meter_instance,
        "meter_key": meter_key,
        "appliances": appliances,
        "sample_period_seconds": 6,
    }


def _quality_row(
    meter_instance: int,
    meter_key: str,
    *,
    start: str,
    end: str,
    sampling_share: float = 0.9,
    quality_error: str | None = None,
    is_mains: bool = False,
) -> dict:
    return {
        "house": 1,
        "meter_instance": meter_instance,
        "meter_key": meter_key,
        "is_mains": is_mains,
        "start": start,
        "end": end,
        "sampling_share": sampling_share,
        "quality_error": quality_error,
    }


def test_excludes_mains_channels_via_is_mains() -> None:

    registry = pd.DataFrame(
        [
            _registry_row(61, "H1_M61", "aggregate"),
            _registry_row(62, "H1_M62", "washer dryer"),
        ]
    )
    quality = pd.DataFrame(
        [
            _quality_row(61, "H1_M61", start="2019-12-01", end="2020-02-01", is_mains=True),
            _quality_row(62, "H1_M62", start="2019-12-01", end="2020-02-01"),
        ]
    )

    result = filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_START, window_end=WINDOW_END)

    assert result["meter_key"].tolist() == ["H1_M62"]


def test_excludes_channels_missing_from_quality() -> None:
    registry = pd.DataFrame(
        [
            _registry_row(62, "H1_M62", "washer dryer"),
            _registry_row(63, "H1_M63", "not canonical, kein Eintrag in channel_quality"),
        ]
    )
    quality = pd.DataFrame([_quality_row(62, "H1_M62", start="2019-12-01", end="2020-02-01")])

    result = filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_START, window_end=WINDOW_END)

    assert result["meter_key"].tolist() == ["H1_M62"]


def test_excludes_presence_untypical_appliances_via_the_hardcoded_list() -> None:
    registry = pd.DataFrame(
        [
            _registry_row(12, "H1_M12", "fridge freezer"),
            _registry_row(5, "H1_M5", "washer dryer"),
        ]
    )
    quality = pd.DataFrame(
        [
            _quality_row(12, "H1_M12", start="2019-12-01", end="2020-02-01"),
            _quality_row(5, "H1_M5", start="2019-12-01", end="2020-02-01"),
        ]
    )

    result = filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_START, window_end=WINDOW_END)

    assert result["meter_key"].tolist() == ["H1_M5"]


def test_excludes_channels_with_quality_error_or_low_sampling_share() -> None:
    registry = pd.DataFrame(
        [
            _registry_row(91, "H1_M91", "dish washer"),
            _registry_row(92, "H1_M92", "microwave"),
            _registry_row(93, "H1_M93", "oven"),
        ]
    )
    quality = pd.DataFrame(
        [
            _quality_row(91, "H1_M91", start="2019-12-01", end="2020-02-01", quality_error="load_failed"),
            _quality_row(92, "H1_M92", start="2019-12-01", end="2020-02-01", sampling_share=0.1),
            _quality_row(93, "H1_M93", start="2019-12-01", end="2020-02-01", sampling_share=0.9),
        ]
    )

    result = filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_START, window_end=WINDOW_END)

    assert result["meter_key"].tolist() == ["H1_M93"]


def test_excludes_channels_that_dont_overlap_the_window() -> None:
    registry = pd.DataFrame([_registry_row(1, "H1_M1", "kettle")])
    quality = pd.DataFrame(
        [_quality_row(1, "H1_M1", start="2018-01-01", end="2018-06-01")]
    )

    result = filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_START, window_end=WINDOW_END)

    assert result.empty


def test_excludes_manually_listed_channels_regardless_of_appliance_name() -> None:
    registry = pd.DataFrame(
        [
            _registry_row(43, "H1_M43", "computer / external hard disk"),
            _registry_row(51, "H1_M51", "desktop computer"),
        ]
    )
    quality = pd.DataFrame(
        [
            _quality_row(43, "H1_M43", start="2019-12-01", end="2020-02-01"),
            _quality_row(51, "H1_M51", start="2019-12-01", end="2020-02-01"),
        ]
    )

    result = filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_START, window_end=WINDOW_END)

    assert result["meter_key"].tolist() == ["H1_M51"]


def test_window_end_must_be_after_window_start() -> None:
    registry = pd.DataFrame([_registry_row(1, "H1_M1", "kettle")])
    quality = pd.DataFrame([_quality_row(1, "H1_M1", start="2019-12-01", end="2020-02-01")])

    with pytest.raises(ValueError, match="window_end"):
        filter_candidate_channels(registry, quality, house=1, window_start=WINDOW_END, window_end=WINDOW_START)


def _hourly_quality(meter_key: str, mask_values: list[bool], *, start: str = "2020-01-01") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(mask_values), freq="1h", tz="UTC")
    return pd.DataFrame({f"{meter_key}_coverage_mask": mask_values}, index=index)


def _hourly_data(meter_key: str, values: list[float], *, start: str = "2020-01-01") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.DataFrame({meter_key: values}, index=index)


def _hourly_mains(values: list[float], *, start: str = "2020-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index, name="mains")


def test_rank_by_coverage_orders_descending_by_activity_share() -> None:
    candidates = pd.DataFrame(
        [
            {"meter_key": "H1_M1", "appliances": "washer dryer"},
            {"meter_key": "H1_M2", "appliances": "dish washer"},
        ]
    )
    quality_a = _hourly_quality("H1_M1", [True, True, True, True], start="2020-01-01")
    quality_b = _hourly_quality("H1_M2", [True, True, True, True], start="2020-01-01")
    quality = quality_a.join(quality_b)
    # gleiche coverage_share (1.0 bei beiden),  activity_share muss trotzdem entscheiden
    data_a = _hourly_data("H1_M1", [0.0, 0.0, 0.0, 0.0], start="2020-01-01")
    data_b = _hourly_data("H1_M2", [10.0, 10.0, 0.0, 0.0], start="2020-01-01")
    data = data_a.join(data_b)
    mains = _hourly_mains([10.0, 10.0, 10.0, 10.0], start="2020-01-01")

    ranked = rank_by_coverage(
        quality,
        data,
        candidates,
        mains,
        window_start=pd.Timestamp("2020-01-01", tz="UTC"),
        window_end=pd.Timestamp("2020-01-01T04:00:00", tz="UTC"),
    )

    assert ranked["meter_key"].tolist() == ["H1_M2", "H1_M1"]
    assert ranked["rank"].tolist() == [1, 2]
    assert ranked.loc[ranked["meter_key"] == "H1_M2", "activity_share"].iloc[0] == 0.5
    assert ranked.loc[ranked["meter_key"] == "H1_M1", "activity_share"].iloc[0] == 0.0


def test_rank_by_coverage_breaks_activity_ties_by_coverage_share() -> None:
    candidates = pd.DataFrame(
        [
            {"meter_key": "H1_M1", "appliances": "washer dryer"},
            {"meter_key": "H1_M2", "appliances": "dish washer"},
        ]
    )
    # gleiche activity_share (0.0 bei beiden), coverage_share entscheidet als Tiebreak
    quality_a = _hourly_quality("H1_M1", [True, True, False, True], start="2020-01-01")
    quality_b = _hourly_quality("H1_M2", [True, True, True, True], start="2020-01-01")
    quality = quality_a.join(quality_b)
    data_a = _hourly_data("H1_M1", [0.0, 0.0, 0.0, 0.0], start="2020-01-01")
    data_b = _hourly_data("H1_M2", [0.0, 0.0, 0.0, 0.0], start="2020-01-01")
    data = data_a.join(data_b)
    mains = _hourly_mains([10.0, 10.0, 10.0, 10.0], start="2020-01-01")

    ranked = rank_by_coverage(
        quality,
        data,
        candidates,
        mains,
        window_start=pd.Timestamp("2020-01-01", tz="UTC"),
        window_end=pd.Timestamp("2020-01-01T04:00:00", tz="UTC"),
    )

    assert ranked["meter_key"].tolist() == ["H1_M2", "H1_M1"]
    assert ranked.loc[ranked["meter_key"] == "H1_M2", "coverage_share"].iloc[0] == 1.0
    assert ranked.loc[ranked["meter_key"] == "H1_M1", "coverage_share"].iloc[0] == 0.75


def test_rank_by_coverage_computes_activity_share_as_mains_consumption_share() -> None:
    candidates = pd.DataFrame([{"meter_key": "H1_M1", "appliances": "washer dryer"}])
    quality = _hourly_quality("H1_M1", [True, True, True, True], start="2020-01-01")
    data = _hourly_data("H1_M1", [20.0, 20.0, 20.0, 20.0], start="2020-01-01")
    mains = _hourly_mains([100.0, 100.0, 100.0, 100.0], start="2020-01-01")

    ranked = rank_by_coverage(
        quality,
        data,
        candidates,
        mains,
        window_start=pd.Timestamp("2020-01-01", tz="UTC"),
        window_end=pd.Timestamp("2020-01-01T04:00:00", tz="UTC"),
    )

    assert ranked["activity_share"].iloc[0] == 0.2


def test_rank_by_coverage_ranks_rare_high_power_channel_above_frequent_low_power_channel() -> None:
    # Spülmaschinen-Fall: läuft nur 1 von 4 Stunden, stellt in der Stunde aber die Hauptlast -
    # ein reiner Aktiv-Stunden-Anteil (alte Logik) hätte das Gegenteil ergeben
    candidates = pd.DataFrame(
        [
            {"meter_key": "H1_M1", "appliances": "HTPC (fast durchgehend an, aber wenig Leistung)"},
            {"meter_key": "H1_M2", "appliances": "dish washer (selten an, viel Leistung)"},
        ]
    )
    quality_a = _hourly_quality("H1_M1", [True, True, True, True], start="2020-01-01")
    quality_b = _hourly_quality("H1_M2", [True, True, True, True], start="2020-01-01")
    quality = quality_a.join(quality_b)
    data_a = _hourly_data("H1_M1", [10.0, 10.0, 10.0, 10.0], start="2020-01-01")
    data_b = _hourly_data("H1_M2", [600.0, 0.0, 0.0, 0.0], start="2020-01-01")
    data = data_a.join(data_b)
    mains = _hourly_mains([700.0, 100.0, 100.0, 100.0], start="2020-01-01")

    ranked = rank_by_coverage(
        quality,
        data,
        candidates,
        mains,
        window_start=pd.Timestamp("2020-01-01", tz="UTC"),
        window_end=pd.Timestamp("2020-01-01T04:00:00", tz="UTC"),
    )

    assert ranked["meter_key"].tolist() == ["H1_M2", "H1_M1"]


def test_rank_by_coverage_treats_missing_channel_as_zero_coverage_and_activity() -> None:
    candidates = pd.DataFrame([{"meter_key": "H1_M9", "appliances": "toaster"}])
    quality = _hourly_quality("H1_M1", [True, True], start="2020-01-01")
    data = _hourly_data("H1_M1", [10.0, 10.0], start="2020-01-01")
    mains = _hourly_mains([10.0, 10.0], start="2020-01-01")

    ranked = rank_by_coverage(
        quality,
        data,
        candidates,
        mains,
        window_start=pd.Timestamp("2020-01-01", tz="UTC"),
        window_end=pd.Timestamp("2020-01-01T02:00:00", tz="UTC"),
    )

    assert ranked["coverage_share"].iloc[0] == 0.0
    assert ranked["activity_share"].iloc[0] == 0.0


def test_rank_by_coverage_treats_zero_mains_as_zero_activity() -> None:
    candidates = pd.DataFrame([{"meter_key": "H1_M1", "appliances": "washer dryer"}])
    quality = _hourly_quality("H1_M1", [True, True], start="2020-01-01")
    data = _hourly_data("H1_M1", [10.0, 10.0], start="2020-01-01")
    mains = _hourly_mains([0.0, 0.0], start="2020-01-01")

    ranked = rank_by_coverage(
        quality,
        data,
        candidates,
        mains,
        window_start=pd.Timestamp("2020-01-01", tz="UTC"),
        window_end=pd.Timestamp("2020-01-01T02:00:00", tz="UTC"),
    )

    assert ranked["activity_share"].iloc[0] == 0.0


def test_rank_by_coverage_returns_empty_frame_for_no_candidates() -> None:
    ranked = rank_by_coverage(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(columns=["meter_key", "appliances"]),
        pd.Series(dtype="float64"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )

    assert ranked.empty