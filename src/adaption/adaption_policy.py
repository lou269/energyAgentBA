from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.common.timestamps import local_isoformat, parse_utc_timestamp, shift_local_days
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


AdaptionActionKind = Literal["none", "advance_history_start", "exclude_window"]


@dataclass(frozen=True)
class AdaptionAction:
    kind: AdaptionActionKind
    new_history_start: pd.Timestamp | None = None
    excluded_window: tuple[pd.Timestamp, pd.Timestamp] | None = None
    reason: str = ""


def adaption_policy(
    classification: Classification,
    context: StructuredState,
    *,
    streak_tolerance_window_days: int,
    window_exclusion: bool,
    local_timezone: str,
) -> AdaptionAction:
    if classification == "new_pattern":
        decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
        new_history_start = pattern_change_start(
            decision_time, streak_tolerance_window_days, local_timezone
        )

        return AdaptionAction(
            kind="advance_history_start",
            new_history_start=new_history_start,
            reason=f"new_pattern, cutting back {streak_tolerance_window_days} days to {local_isoformat(new_history_start, local_timezone)}",
        )

    if classification == "absence" and window_exclusion:
        return absence_action(context, local_timezone)

    if classification == "measurement_error" and window_exclusion:
        return measurement_error_action(context, local_timezone)

    return AdaptionAction(kind="none", reason=f"{classification}: no action")


# das LLM nennt nur die Klasse, Anfang und Ende der Abwesenheit kommen aus dem Kalendereintrag
def absence_action(context: StructuredState, local_timezone: str) -> AdaptionAction:
    decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
    last_analyzed_hour = decision_time - pd.Timedelta(hours=1)

    for event in context["context"]["events"]:
        start = parse_utc_timestamp(event["start"], "start")
        end = parse_utc_timestamp(event["end"], "end")

        if event["event_type"] == "absence" and start <= last_analyzed_hour < end:
            return AdaptionAction(
                kind="exclude_window",
                excluded_window=(start, end),
                reason=f"absence, excluding {event['event_id']} from {local_isoformat(start, local_timezone)} to {local_isoformat(end, local_timezone)}",
            )

    return AdaptionAction(
        kind="none", reason="absence without a matching calendar event: no action"
    )


# nur der analysierte Tag, ein Festhänger über Mitternacht wird am Folgetag selbst nochmal erkannt
def measurement_error_action(
    context: StructuredState, local_timezone: str
) -> AdaptionAction:
    decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
    day_start = shift_local_days(decision_time, -1, local_timezone)

    return AdaptionAction(
        kind="exclude_window",
        excluded_window=(day_start, decision_time),
        reason=f"measurement_error, excluding {local_isoformat(day_start, local_timezone)[:10]}",
    )


# ausgeschlossene Tage werden zu Lücken wie ein unvollständiger Tag, ab keep_from bleibt alles drin (der analysierte Tag selbst)
def mask_excluded_windows(
    history: pd.Series,
    excluded_windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...],
    keep_from: pd.Timestamp | None = None,
) -> pd.Series:
    masked = history.copy()

    for start, end in excluded_windows:
        in_window = (masked.index >= start) & (masked.index < end)
        if keep_from is not None:
            in_window &= masked.index < keep_from
        masked.loc[in_window] = float("nan")

    return masked


# t_c pauschal am Anfang des Streak-Fensters, das LLM liefert keinen eigenen Zeitpunkt
def pattern_change_start(
    decision_time: pd.Timestamp, streak_tolerance_window_days: int, local_timezone: str
) -> pd.Timestamp:
    return shift_local_days(
        decision_time, -streak_tolerance_window_days, local_timezone
    )
