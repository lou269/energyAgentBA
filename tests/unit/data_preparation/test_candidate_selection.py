# python -m pytest tests/unit/data_preparation/test_candidate_selection.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.data_preparation.selection.candidate_selection import build_candidate_selection


def _registry(
    rows: list[tuple[int, int, str, str]]
) -> pd.DataFrame:
    
    return pd.DataFrame(rows, columns=["house", "meter_instance", "meter_key", "meter_type"])


def test_single_house_picks_longest_eligible_span() -> None:
    availability = pd.DataFrame(
        [
            {"meter_key": "m1", "start": "2020-01-01", "end": "2020-02-01", "length_days": 31.0, "coverage_share": 0.99},
            {"meter_key": "m1", "start": "2020-03-01", "end": "2020-03-10", "length_days": 9.0, "coverage_share": 0.99},
        ]
    )
    registry = _registry([(1, 54, "m1", "mains")])

    selection, decisions = build_candidate_selection(
        availability, registry, min_valid_duration_days=5.0, min_coverage_share=0.8
    )

    assert len(selection) == 1
    assert selection.iloc[0]["window_start"] == "2020-01-01"

    winner_row = decisions.loc[decisions["candidate_id"].eq(selection.iloc[0]["candidate_id"])].iloc[0]
    assert winner_row["selection_rank"] == 1
    assert bool(winner_row["selected"]) is True


def test_best_span_wins_regardless_of_house() -> None:
    availability = pd.DataFrame(
        [
            {"meter_key": "m1", "start": "2020-01-01", "end": "2020-01-31", "length_days": 30.0, "coverage_share": 0.99},
            {"meter_key": "m2", "start": "2019-01-01", "end": "2019-03-01", "length_days": 60.0, "coverage_share": 0.99},
        ]
    )
    registry = _registry([(1, 54, "m1", "mains"), (2, 1, "m2", "mains")])

    selection, decisions = build_candidate_selection(
        availability, registry, min_valid_duration_days=5.0, min_coverage_share=0.8
    )

    # nur EIN Kandidat wird gewählt, unabhängig vom Haus - der mit der längsten Spanne
    assert len(selection) == 1
    assert selection.iloc[0]["candidate_id"].startswith("H2-M1-")
    assert (decisions["selected"].sum()) == 1


def test_spans_below_threshold_are_rejected_with_reason() -> None:
    availability = pd.DataFrame(
        [
            {"meter_key": "m1", "start": "2020-01-01", "end": "2020-01-03", "length_days": 3.0, "coverage_share": 0.99},
            {"meter_key": "m1", "start": "2020-02-01", "end": "2020-02-20", "length_days": 20.0, "coverage_share": 0.5},
        ]
    )
    registry = _registry([(1, 54, "m1", "mains")])

    selection, decisions = build_candidate_selection(
        availability, registry, min_valid_duration_days=10.0, min_coverage_share=0.8
    )

    assert selection.empty
    assert not decisions.empty
    assert not decisions["selected"].any()
    reasons = dict(zip(decisions["length_days"], decisions["decision_reason"]))
    assert reasons[3.0] == "length_below_threshold"
    assert reasons[20.0] == "coverage_below_threshold"


def test_submeter_channels_are_excluded() -> None:
    availability = pd.DataFrame(
        [
            {"meter_key": "mains1", "start": "2020-01-01", "end": "2020-02-01", "length_days": 31.0, "coverage_share": 0.99},
            {"meter_key": "aux1", "start": "2020-01-01", "end": "2020-06-01", "length_days": 150.0, "coverage_share": 0.99},
        ]
    )
    registry = _registry([(1, 54, "mains1", "mains"), (1, 3, "aux1", "submeter")])

    selection, decisions = build_candidate_selection(
        availability, registry, min_valid_duration_days=5.0, min_coverage_share=0.8
    )

    assert (decisions["meter_key"] == "aux1").sum() == 0
    assert selection.iloc[0]["candidate_id"].startswith("H1-M54-")


def test_rejects_invalid_thresholds() -> None:
    availability = pd.DataFrame(columns=["meter_key", "start", "end", "length_days", "coverage_share"])
    registry = _registry([])

    with pytest.raises(ValueError):
        build_candidate_selection(availability, registry, min_valid_duration_days=0.0, min_coverage_share=0.8)

    with pytest.raises(ValueError):
        build_candidate_selection(availability, registry, min_valid_duration_days=5.0, min_coverage_share=1.5)
