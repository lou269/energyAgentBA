# python -m pytest tests/unit/data_preparation/test_candidate_availability.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.data_preparation.selection.candidate_availability import build_candidate_availability


def _hourly_frame(covered: list[bool]) -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2020-01-01", periods=len(covered), freq="1h")
    data = pd.DataFrame({"meter": [1.0 if c else None for c in covered]}, index=index)
    quality = pd.DataFrame({"meter_coverage_mask": covered}, index=index)
    return data, quality


def test_short_gap_does_not_split_span() -> None:
    # 5 belegt, 2 fehlend (Toleranz), 5 belegt -> soll EINE Spanne bleiben
    covered = [True] * 5 + [False] * 2 + [True] * 5
    data, quality = _hourly_frame(covered)

    availability = build_candidate_availability(data, quality, max_gap_intervals=2)

    assert len(availability) == 1
    row = availability.iloc[0]
    assert row["length_days"] == pytest.approx(12 / 24)
    assert row["coverage_share"] == pytest.approx(10 / 12)


def test_long_gap_splits_into_two_spans() -> None:
    # 5 belegt, 3 fehlend (ueber Toleranz), 5 belegt -> ZWEI Spannen
    covered = [True] * 5 + [False] * 3 + [True] * 5
    data, quality = _hourly_frame(covered)

    availability = build_candidate_availability(data, quality, max_gap_intervals=2)

    assert len(availability) == 2
    assert availability["length_days"].tolist() == [pytest.approx(5 / 24), pytest.approx(5 / 24)]
    assert (availability["coverage_share"] == 1.0).all()


def test_fully_missing_channel_has_no_spans() -> None:
    data, quality = _hourly_frame([False] * 10)

    availability = build_candidate_availability(data, quality, max_gap_intervals=2)

    assert availability.empty


def test_channels_are_evaluated_independently() -> None:
    index = pd.date_range("2020-01-01", periods=6, freq="1h")
    data = pd.DataFrame(
        {"a": [1.0] * 6, "b": [1.0, None, None, None, None, 1.0]},
        index=index,
    )
    quality = pd.DataFrame(
        {
            "a_coverage_mask": [True] * 6,
            "b_coverage_mask": [True, False, False, False, False, True],
        },
        index=index,
    )

    availability = build_candidate_availability(data, quality, max_gap_intervals=2)

    assert set(availability["meter_key"]) == {"a", "b"}
    assert len(availability[availability["meter_key"] == "a"]) == 1
    # Lücke von 4 Stunden > Toleranz 2 -> Kanal b fällt in zwei Ein-Punkt-Spannen
    assert len(availability[availability["meter_key"] == "b"]) == 2
