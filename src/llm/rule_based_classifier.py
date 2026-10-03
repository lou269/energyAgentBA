from dataclasses import dataclass

from src.common.timestamps import analyzed_day, parse_utc_timestamp
from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


@dataclass(frozen=True)
class RuleClassificationResult:
    classification: Classification
    reasoning: str


def rule_based_classify(
    state: StructuredState,
    *,
    local_timezone: str,
    min_sustained_scales: int,
) -> RuleClassificationResult:
    observation = state["observation"]
    anomaly = state["anomaly"]

    decision_time = parse_utc_timestamp(state["decision_time"], "decision_time")
    # nur für die reasoning-Texte gedacht (Nachvollziehbarkeit), fließt in keine Entscheidung ein
    day_label = (
        "weekend"
        if analyzed_day(decision_time, local_timezone).dayofweek >= 5
        else "weekday"
    )

    if observation["value_implausible"]:
        return RuleClassificationResult(
            classification="measurement_error",
            reasoning=f"observation.value_implausible is set ({day_label}).",
        )

    if len(anomaly["sustained_scales"]) >= min_sustained_scales:
        return RuleClassificationResult(
            classification="new_pattern",
            reasoning=f"sustained deviation across multiple scales at once ({', '.join(anomaly['sustained_scales'])}), on a {day_label}.",
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
