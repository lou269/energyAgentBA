from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE
from src.common.timestamps import (
    local_isoformat,
    local_midnight_utc,
    parse_utc_timestamp,
)


def load_calendar_events(path: Path) -> tuple[Mapping[str, object], ...]:
    events = json.loads(path.read_text(encoding="utf-8"))

    # in der Datei steht Ortszeit ohne Offset, Sommer- oder Winterzeit ergibt sich erst hier
    for event in events:
        for field in ("start", "end", "known_at"):
            event[field] = local_isoformat(
                local_midnight_utc(event[field], LOCAL_TIMEZONE), LOCAL_TIMEZONE
            )

    return tuple(events)


def resolve_absence_window(
    events: tuple[Mapping[str, object], ...],
    event_id: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    matches = [event for event in events if event.get("event_id") == event_id]

    if not matches:
        raise ValueError(f"No calendar event with event_id={event_id!r} found.")

    event = matches[0]
    return parse_utc_timestamp(str(event["start"]), "start"), parse_utc_timestamp(
        str(event["end"]), "end"
    )


def channels_meeting_thresholds(
    ranking: pd.DataFrame,
    *,
    min_coverage_share: float,
) -> pd.Series:
    return ranking[
        "coverage_share"
    ].ge(
        min_coverage_share
    )  # activity_share zählt nicht rein, seltene aber starke Geräte sollen nicht rausfallen
