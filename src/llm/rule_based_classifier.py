from dataclasses import dataclass

from src.common.timestamps import parse_utc_timestamp
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


@dataclass(frozen=True)
class RuleClassificationResult:
    classification: Classification
    reasoning: str


def rule_based_classify(
    state: StructuredState,
    *,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
    local_timezone: str,
)-> RuleClassificationResult:
    # run_cycle ruft das nur bei anomaly.level != "normal" auf (Z-Score-Gate) -> "normal" kommt hier garnicht mehr vor
    observation = state["observation"]
    anomaly = state["anomaly"]

    assert anomaly["level"] != "normal"

    decision_time = parse_utc_timestamp(state["decision_time"], "decision_time")
    # nur für die reasoning-Texte gedacht (Nachvollziehbarkeit), fließt in keine Entscheidung ein
    day_label = "weekend" if decision_time.tz_convert(local_timezone).dayofweek >= 5 else "weekday"

    if observation["value_implausible"]:
        return RuleClassificationResult(
            classification="measurement_error",
            reasoning=f"observation.value_implausible is set ({day_label}).",
        )

    scale_streak_days = anomaly["scale_anomaly_streak_days"]

    sustained_scales = [
        scale
        for scale in anomaly["available_scales"]
        if (streak_days := scale_streak_days[scale]) is not None and streak_days >= sustained_anomaly_streak_days
    ]

    if len(sustained_scales) >= min_sustained_scales:
        return RuleClassificationResult(
            classification="new_pattern",
            reasoning=f"sustained deviation across multiple scales at once ({', '.join(sustained_scales)}), on a {day_label}.",
        )

    # peak/low sind per Definition richtungsgebunden ("unusually high"/"unusually low" consumption), ohne sustained Mehrskalen-Signatur bleibt nur die Richtung, um zwischen beiden zu unterscheiden
    if anomaly["direction"] == "high":
        return RuleClassificationResult(
            classification="peak",
            reasoning=f"unusual ({anomaly['level']}), but no sustained multi-scale signature ({day_label}).",
        )

    return RuleClassificationResult(
        classification="low",
        reasoning=f"unusual ({anomaly['level']}) low reading, but no sustained multi-scale signature ({day_label}).",
    )

