from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.common.timestamps import parse_utc_timestamp
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
    context: StructuredState,
) -> AdaptionAction:
    if classification == "measurement_error":
        timestamp = parse_utc_timestamp(context["observation"]["observation_start"], "observation.observation_start")
        return AdaptionAction(
            kind="exclude_range",
            range_start=timestamp,
            range_end=timestamp,
            reason=f"measurement_error at {timestamp.isoformat()}",
        )

    if classification == "absence":
        decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
        streak_days = _dominant_streak_days(context)
        range_end = decision_time - pd.Timedelta(hours=1)
        window_start = range_end - pd.Timedelta(hours=streak_days * 24 - 1)

        return AdaptionAction(
            kind="exclude_range",
            range_start=window_start,
            range_end=range_end,
            reason=f"absence over the last {streak_days:.0f} days up to {range_end.isoformat()}",
        )

    if classification == "new_pattern":
        decision_time = parse_utc_timestamp(context["decision_time"], "decision_time")
        streak_days = _dominant_streak_days(context)
        range_end = decision_time - pd.Timedelta(hours=1)
        new_history_start = range_end - pd.Timedelta(hours=streak_days * 24 - 1)

        return AdaptionAction(
            kind="advance_history_start",
            new_history_start=new_history_start,
            reason=f"new_pattern since {new_history_start.isoformat()} ({streak_days:.0f} days sustained)",
        )

    return AdaptionAction(kind="none", reason=f"{classification}: no action")


def _dominant_streak_days(
    context: StructuredState
) -> float:
    dominant_scale = context["anomaly"]["dominant_scale"]

    if dominant_scale is None:
        raise ValueError("anomaly.dominant_scale is missing for this classification.")

    streak_days = context["anomaly"]["scale_anomaly_streak_days"][dominant_scale]

    if streak_days is None:
        raise ValueError("anomaly.scale_anomaly_streak_days for the dominant scale is missing.")

    return streak_days