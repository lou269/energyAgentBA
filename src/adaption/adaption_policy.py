from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


AdaptionActionKind = Literal["none", "advance_history_start", "exclude_range"]


@dataclass(frozen=True)
class AdaptionAction:
    kind: AdaptionActionKind
    range_start: pd.Timestamp | None = None
    range_end: pd.Timestamp | None = None
    new_history_start: pd.Timestamp | None = None
    reason: str = ""


def adaption_policy(
    classification: Classification, 
    context: StructuredState
) -> AdaptionAction:
    if classification == "measurement_error":
        timestamp = _timestamp(context["observation"]["observation_start"])
        return AdaptionAction(
            kind="exclude_range",
            range_start=timestamp,
            range_end=timestamp,
            reason=f"measurement_error at {timestamp.isoformat()}",
        )

    if classification == "absence":
        decision_time = _timestamp(context["decision_time"])
        streak_hours = _dominant_streak_hours(context)
        range_start = decision_time - pd.Timedelta(hours=streak_hours)

        return AdaptionAction(
            kind="exclude_range",
            range_start=range_start,
            range_end=decision_time - pd.Timedelta(hours=1),
            reason=f"absence since {range_start.isoformat()} ({streak_hours:.0f}h)",
        )

    if classification == "new_pattern":
        decision_time = _timestamp(context["decision_time"])
        streak_hours = _dominant_streak_hours(context)
        new_history_start = decision_time - pd.Timedelta(hours=streak_hours)

        return AdaptionAction(
            kind="advance_history_start",
            new_history_start=new_history_start,
            reason=f"new_pattern since {new_history_start.isoformat()} ({streak_hours:.0f}h)",
        )

    return AdaptionAction(kind="none", reason=f"{classification}: no action")


def _dominant_streak_hours(
    context: StructuredState
) -> float:
    dominant_scale = context["anomaly"]["dominant_scale"]

    if dominant_scale is None:
        raise ValueError("anomaly.dominant_scale is missing for this classification.")

    streak_hours = context["anomaly"]["scale_streak_hours"][dominant_scale]

    if streak_hours is None:
        raise ValueError("anomaly.scale_streak_hours for the dominant scale is missing.")

    return streak_hours


def _timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC")