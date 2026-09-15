from dataclasses import dataclass

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
    multi_scale_minimum: int,
)-> RuleClassificationResult:
    # run_cycle ruft das nur bei anomaly.level != "normal" auf (Z-Score-Gate) -> "normal" kommt hier garnicht mehr vor
    observation = state["observation"]
    anomaly = state["anomaly"]

    assert anomaly["level"] != "normal"

    if observation["value_implausible"]:
        return RuleClassificationResult(
            classification="measurement_error",
            reasoning="observation.value_implausible is set.",
        )

    scale_streak_days = anomaly["scale_anomaly_streak_days"]

    sustained_scales = [
        scale
        for scale in anomaly["available_scales"]
        if (streak_days := scale_streak_days[scale]) is not None and streak_days >= sustained_anomaly_streak_days
    ]

    dominant_scale = anomaly["dominant_scale"]

    if (
        anomaly["level"] == "strong_anomaly"
        and anomaly["direction"] == "low"
        and dominant_scale in sustained_scales
    ):
        return RuleClassificationResult(
            classification="absence",
            reasoning=(
                f"strong, sustained downward deviation on scale '{dominant_scale}' ({scale_streak_days[dominant_scale]:.0f} days elevated in a row >= {sustained_anomaly_streak_days})."
            ),
        )

    if len(sustained_scales) >= multi_scale_minimum:
        return RuleClassificationResult(
            classification="new_pattern",
            reasoning=f"sustained deviation across multiple scales at once ({', '.join(sustained_scales)}).",
        )

    return RuleClassificationResult(
        classification="peak",
        reasoning=f"unusual ({anomaly['level']}), but no sustained absence or multi-scale signature.",
    )


