from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.common.timestamps import parse_utc_timestamp
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
) -> AdaptionAction:
    # measurement_error braucht hier keine eigene Aktion: der Tag ist zu diesem Zeitpunkt schon durch
    # exclude_incomplete_days() (Preprocessing) komplett aus history raus, nichts mehr zu excluden
    if classification == "new_pattern":
        decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
        range_end = decision_time - pd.Timedelta(hours=1)
        new_history_start = range_end - pd.Timedelta(hours=streak_tolerance_window_days * 24 - 1)

        return AdaptionAction(
            kind="advance_history_start",
            new_history_start=new_history_start,
            reason=f"new_pattern, cutting back {streak_tolerance_window_days} days to {new_history_start.isoformat()}",
        )

    return AdaptionAction(kind="none", reason=f"{classification}: no action")