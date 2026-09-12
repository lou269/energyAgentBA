from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pandas as pd

from experiments.proposal_experiments.e2_absence.e2_config import MIN_COVERAGE_SHARE_FOR_SUBTRACTION

def load_calendar_events(path: Path) -> tuple[Mapping[str, object], ...]:
    events = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(events, list):
        raise TypeError(f"{path} must contain a JSON array of calendar events.")

    return tuple(events)


def resolve_absence_window(
    events: tuple[Mapping[str, object], ...],
    event_id: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    matches = [event for event in events if event.get("event_id") == event_id]

    if not matches:
        raise ValueError(f"No calendar event with event_id={event_id!r} found.")

    event = matches[0]

    return pd.Timestamp(str(event["start"])), pd.Timestamp(str(event["end"]))


def build_decision_times(
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    *,
    margin_before_days: int,
    margin_after_days: int,
) -> tuple[pd.Timestamp, ...]:
    start = window_start - pd.Timedelta(days=margin_before_days)
    end = window_end + pd.Timedelta(days=margin_after_days)

    return tuple(pd.date_range(start, end, freq="24h", tz="UTC"))


def channels_meeting_thresholds(
    ranking: pd.DataFrame,
    *,
    min_coverage_share: float = MIN_COVERAGE_SHARE_FOR_SUBTRACTION,
) -> pd.Series:
    # activity_share fließt hier bewusst nicht ein - seltene, aber hochleistungsstarke Präsenzgeräte
    # (z.B. Spülmaschine) sollen nicht rausfallen, siehe rank_by_coverage
    return ranking["coverage_share"].ge(min_coverage_share)


def select_channels_for_subtraction(
    ranking: pd.DataFrame,
    *,
    min_coverage_share: float = MIN_COVERAGE_SHARE_FOR_SUBTRACTION,
) -> list[str]:
    if ranking.empty:
        raise ValueError("ranking is empty - no candidate channels available for the target window.")

    selected = ranking.loc[
        channels_meeting_thresholds(ranking, min_coverage_share=min_coverage_share),
        "meter_key",
    ].tolist()

    if not selected:
        raise ValueError(f"No candidate channel reaches min_coverage_share={min_coverage_share} in the target window.")

    return selected