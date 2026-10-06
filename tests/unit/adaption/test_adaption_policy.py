# python -m pytest tests/unit/adaption/test_adaption_policy.py -v


from typing import cast

import pandas as pd
import pytest

from src.adaption.adaption_policy import (
    AdaptionAction,
    adaption_policy,
    add_excluded_window,
    apply_adaption,
    ended_windows,
    mask_excluded_windows,
)
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# minimaler Kontext, adaption_policy liest nur decision_time und die Kalendereinträge
def _context(
    *, decision_time: str, events: list[dict] | None = None
) -> StructuredState:
    return cast(
        StructuredState,
        {
            "decision_time": decision_time,
            "context": {"events": events or []},
        },
    )


def _event() -> dict:
    return {
        "event_id": "event-test",
        "title": "Urlaub bei Oma",
        "start": "2013-09-14T00:00:00+00:00",
        "end": "2013-09-28T00:00:00+00:00",
        "known_at": "2013-08-14T00:00:00+00:00",
    }


def test_new_pattern_advances_the_history_start_by_the_tolerance_window() -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00")

    action = adaption_policy(
        "new_pattern",
        context,
        streak_tolerance_window_days=2,
        window_exclusion=True,
        local_timezone="UTC",
    )

    assert action.kind == "advance_history_start"
    assert action.new_history_start is not None
    # 2 Kalendertage vor decision_time
    assert action.new_history_start.isoformat() == "2024-01-05T10:00:00+00:00"


@pytest.mark.parametrize("classification", ["peak", "low", "normal", "unknown"])
def test_classifications_without_a_defined_reaction_trigger_no_action(
    classification: Classification,
) -> None:
    context = _context(decision_time="2024-01-07T10:00:00+00:00")

    action = adaption_policy(
        classification,
        context,
        streak_tolerance_window_days=7,
        window_exclusion=True,
        local_timezone="UTC",
    )

    assert action.kind == "none"


def test_absence_excludes_the_whole_calendar_window_not_only_the_analyzed_day() -> None:
    # erkannt erst am 26.09., ausgeschlossen wird trotzdem ab dem 14.09.
    context = _context(decision_time="2013-09-27T00:00:00+00:00", events=[_event()])

    action = adaption_policy(
        "absence",
        context,
        streak_tolerance_window_days=7,
        window_exclusion=True,
        local_timezone="UTC",
    )

    assert action.kind == "exclude_window"
    assert action.excluded_window == (
        pd.Timestamp("2013-09-14T00:00:00+00:00"),
        pd.Timestamp("2013-09-28T00:00:00+00:00"),
    )


def test_absence_without_a_matching_calendar_event_triggers_no_action() -> None:
    # analysierter Tag 28.09. liegt schon hinter dem Ende
    context = _context(decision_time="2013-09-29T00:00:00+00:00", events=[_event()])

    action = adaption_policy(
        "absence",
        context,
        streak_tolerance_window_days=7,
        window_exclusion=True,
        local_timezone="UTC",
    )

    assert action.kind == "none"


def test_measurement_error_excludes_only_the_analyzed_day() -> None:
    context = _context(decision_time="2013-09-27T00:00:00+00:00")

    action = adaption_policy(
        "measurement_error",
        context,
        streak_tolerance_window_days=7,
        window_exclusion=True,
        local_timezone="UTC",
    )

    assert action.kind == "exclude_window"
    assert action.excluded_window == (
        pd.Timestamp("2013-09-26T00:00:00+00:00"),
        pd.Timestamp("2013-09-27T00:00:00+00:00"),
    )


@pytest.mark.parametrize("classification", ["absence", "measurement_error"])
def test_without_window_exclusion_nothing_is_excluded(
    classification: Classification,
) -> None:
    context = _context(decision_time="2013-09-27T00:00:00+00:00", events=[_event()])

    action = adaption_policy(
        classification,
        context,
        streak_tolerance_window_days=7,
        window_exclusion=False,
        local_timezone="UTC",
    )

    assert action.kind == "none"


def test_mask_excluded_windows_keeps_the_analyzed_day_and_everything_outside() -> None:
    index = pd.date_range("2013-09-13", periods=4 * 24, freq="1h", tz="UTC")
    history = pd.Series(100.0, index=index)
    window = (
        pd.Timestamp("2013-09-14", tz="UTC"),
        pd.Timestamp("2013-09-28", tz="UTC"),
    )

    masked = mask_excluded_windows(
        history, (window,), keep_from=pd.Timestamp("2013-09-16", tz="UTC")
    )

    daily_valid = masked.notna().groupby(pd.DatetimeIndex(masked.index).date).sum()
    assert daily_valid.tolist() == [24, 0, 0, 24]


def test_a_running_absence_stays_in_training_until_its_end() -> None:
    vacation = (
        pd.Timestamp("2013-09-14", tz="UTC"),
        pd.Timestamp("2013-09-28", tz="UTC"),
    )
    stuck_day = (
        pd.Timestamp("2013-09-15", tz="UTC"),
        pd.Timestamp("2013-09-16", tz="UTC"),
    )

    assert ended_windows(
        (vacation, stuck_day), pd.Timestamp("2013-09-16", tz="UTC")
    ) == (stuck_day,)
    # erster Tag nach der Rückkehr
    assert ended_windows((vacation,), pd.Timestamp("2013-09-28", tz="UTC")) == (
        vacation,
    )


def test_add_excluded_window_skips_duplicates() -> None:
    vacation = (
        pd.Timestamp("2013-09-14", tz="UTC"),
        pd.Timestamp("2013-09-28", tz="UTC"),
    )
    action = AdaptionAction(kind="exclude_window", excluded_window=vacation)

    windows, first = add_excluded_window((), action)
    assert windows == (vacation,)
    assert first.kind == "exclude_window"

    windows, second = add_excluded_window(windows, action)
    assert windows == (vacation,)
    assert second.kind == "none"


def test_apply_adaption_cuts_history() -> None:
    index = pd.date_range("2013-09-13", periods=3 * 24, freq="1h", tz="UTC")
    history = pd.Series(100.0, index=index)
    start = pd.Timestamp("2013-09-14", tz="UTC")

    cut = apply_adaption(
        history,
        AdaptionAction(kind="advance_history_start", new_history_start=start),
    )

    assert cut.index[0] == start
    assert len(cut) == 2 * 24
