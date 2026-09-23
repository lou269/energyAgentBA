from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.common.timestamps import local_isoformat, parse_utc_timestamp, shift_local_days
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


AdaptionActionKind = Literal["none", "advance_history_start"]


@dataclass(frozen=True)
class AdaptionAction:
    kind: AdaptionActionKind
    new_history_start: pd.Timestamp | None = None
    reason: str = ""


def adaption_policy(
    classification: Classification,
    context: StructuredState,
    *,
    streak_tolerance_window_days: int,
    local_timezone: str,
) -> AdaptionAction:
    # measurement_error braucht hier keine eigene Aktion: der Tag ist zu diesem Zeitpunkt schon durch
    # exclude_incomplete_days() (Preprocessing) komplett aus history raus, nichts mehr zu excluden
    if classification == "new_pattern":
        decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
        new_history_start = pattern_change_start(decision_time, streak_tolerance_window_days, local_timezone)

        return AdaptionAction(
            kind="advance_history_start",
            new_history_start=new_history_start,
            reason=f"new_pattern, cutting back {streak_tolerance_window_days} days to {local_isoformat(new_history_start, local_timezone)}",
        )

    return AdaptionAction(kind="none", reason=f"{classification}: no action")


# t_c pauschal am Anfang des Streak-Fensters, das LLM liefert keinen eigenen Zeitpunkt
def pattern_change_start(decision_time: pd.Timestamp, streak_tolerance_window_days: int, local_timezone: str) -> pd.Timestamp:
    return shift_local_days(decision_time, -streak_tolerance_window_days, local_timezone)