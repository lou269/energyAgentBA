# python -m pytest tests/unit/proposal_experiments/e2_absence/test_e2_selection.py -v

import pandas as pd
import pytest

from experiments.proposal_experiments.e_config import E2Config
from experiments.proposal_experiments.e2_absence.e2_selection import channels_meeting_thresholds, load_calendar_events, resolve_absence_window, select_channels_for_subtraction


E2_CONFIG = E2Config()


def test_resolve_absence_window_matches_e2_config_reference() -> None:
    events = load_calendar_events(E2_CONFIG.calendar_events_file, "Europe/London")

    window_start, window_end = resolve_absence_window(events, E2_CONFIG.active_absence_event_id)

    assert window_start == pd.Timestamp("2013-06-06T00:00:00+01:00")
    assert window_end == pd.Timestamp("2013-06-13T00:00:00+01:00")


def test_resolve_absence_window_raises_for_unknown_event_id() -> None:
    events = ({"event_id": "known", "start": "2020-01-01T00:00:00+00:00", "end": "2020-01-02T00:00:00+00:00"},)

    with pytest.raises(ValueError, match="unknown"):
        resolve_absence_window(events, "unknown")


def test_channels_meeting_thresholds_ignores_activity_share() -> None:
    # Spülmaschinen-Fall: niedrige activity_share, aber hohe coverage_share(-> soll trotzdem ausgesucht werden)
    ranking = pd.DataFrame(
        [
            {"meter_key": "H1_M6", "coverage_share": 1.0, "activity_share": 0.036},
            {"meter_key": "H1_M9", "coverage_share": 0.5, "activity_share": 0.3},
        ]
    )

    selected = channels_meeting_thresholds(ranking, min_coverage_share=0.9)

    assert selected.tolist() == [True, False]


def test_select_channels_for_subtraction_filters_by_coverage_only() -> None:
    ranking = pd.DataFrame(
        [
            {"meter_key": "H1_M6", "coverage_share": 1.0, "activity_share": 0.036},
            {"meter_key": "H1_M9", "coverage_share": 0.5, "activity_share": 0.3},
        ]
    )

    selected = select_channels_for_subtraction(ranking, min_coverage_share=0.9)

    assert selected == ["H1_M6"]


def test_select_channels_for_subtraction_raises_when_none_reach_coverage() -> None:
    ranking = pd.DataFrame([{"meter_key": "H1_M9", "coverage_share": 0.5, "activity_share": 0.3}])

    with pytest.raises(ValueError, match="min_coverage_share"):
        select_channels_for_subtraction(ranking, min_coverage_share=0.9)