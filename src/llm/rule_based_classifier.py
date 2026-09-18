from dataclasses import dataclass

import pandas as pd

from src.common.timestamps import parse_utc_timestamp
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import ContextState, StructuredState


@dataclass(frozen=True)
class RuleClassificationResult:
    classification: Classification
    reasoning: str


def rule_based_classify(
    state: StructuredState,
    *,
    sustained_anomaly_streak_days: int,
    multi_scale_minimum: int,
    local_timezone: str,
)-> RuleClassificationResult:
    # run_cycle ruft das nur bei anomaly.level != "normal" auf (Z-Score-Gate) -> "normal" kommt hier garnicht mehr vor
    observation = state["observation"]
    anomaly = state["anomaly"]
    context = state["context"]

    assert anomaly["level"] != "normal"

    decision_time = parse_utc_timestamp(state["decision_time"], "decision_time")
    # nur für die reasoning-Texte gedacht (Nachvollziehbarkeit), fließt in keine Entscheidung ein
    day_label = "weekend" if decision_time.tz_convert(local_timezone).dayofweek >= 5 else "weekday"

    if observation["value_implausible"]:
        return RuleClassificationResult(
            classification="measurement_error",
            reasoning=f"observation.value_implausible is set ({day_label}).",
        )

    if _has_absence_event(context, decision_time):
        return RuleClassificationResult(
            classification="absence",
            reasoning=f"calendar event confirms absence covering {decision_time.isoformat()} ({day_label}).",
        )

    scale_streak_days = anomaly["scale_anomaly_streak_days"]

    sustained_scales = [
        scale
        for scale in anomaly["available_scales"]
        if (streak_days := scale_streak_days[scale]) is not None and streak_days >= sustained_anomaly_streak_days
    ]

    if len(sustained_scales) >= multi_scale_minimum:
        return RuleClassificationResult(
            classification="new_pattern",
            reasoning=f"sustained deviation across multiple scales at once ({', '.join(sustained_scales)}), on a {day_label}.",
        )

    return RuleClassificationResult(
        classification="peak",
        reasoning=f"unusual ({anomaly['level']}), but no sustained absence or multi-scale signature ({day_label}).",
    )


def _has_absence_event(context: ContextState, decision_time: pd.Timestamp) -> bool:
    if not context["source_available"]:
        return False

    for event in context["events"]:
        if event["event_type"] != "absence":
            continue

        start = parse_utc_timestamp(event["start"], "event.start")
        end = parse_utc_timestamp(event["end"], "event.end")

        if start <= decision_time < end:
            return True

    return False

