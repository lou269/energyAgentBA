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
        elevated_hours = _dominant_elevated_hours(context)
        day_start = (decision_time - pd.Timedelta(hours=1)).normalize()

        return AdaptionAction(
            kind="exclude_range",
            range_start=day_start,
            range_end=decision_time - pd.Timedelta(hours=1),
            reason=f"absence on {day_start.date()} ({elevated_hours:.0f}h elevated today)",
        )

    if classification == "new_pattern":
        decision_time = _timestamp(context["decision_time"])
        elevated_hours = _dominant_elevated_hours(context)
        new_history_start = (decision_time - pd.Timedelta(hours=1)).normalize()

        return AdaptionAction(
            kind="advance_history_start",
            new_history_start=new_history_start,
            reason=f"new_pattern since {new_history_start.date()} ({elevated_hours:.0f}h elevated that day)",
        )

    return AdaptionAction(kind="none", reason=f"{classification}: no action")


def _dominant_elevated_hours(
    context: StructuredState
) -> float:
    dominant_scale = context["anomaly"]["dominant_scale"]

    if dominant_scale is None:
        raise ValueError("anomaly.dominant_scale is missing for this classification.")

    elevated_hours = context["anomaly"]["scale_elevated_hours"][dominant_scale]

    if elevated_hours is None:
        raise ValueError("anomaly.scale_elevated_hours for the dominant scale is missing.")

    return elevated_hours


def _timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC")