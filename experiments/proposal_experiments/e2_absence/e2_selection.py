from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pandas as pd


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


def channels_meeting_thresholds(
    ranking: pd.DataFrame,
    *,
    min_coverage_share: float,
) -> pd.Series:
    return ranking["coverage_share"].ge(min_coverage_share) # activity_share zählt nicht rein, seltene aber starke Geräte sollen nicht rausfallen


def select_channels_for_subtraction(
    ranking: pd.DataFrame,
    *,
    min_coverage_share: float,
) -> list[str]:
    selected = ranking.loc[
        channels_meeting_thresholds(ranking, min_coverage_share=min_coverage_share), "meter_key"
    ].tolist()

    if not selected:
        raise ValueError(f"No candidate channel reaches min_coverage_share={min_coverage_share} in the target window.")

    return selected