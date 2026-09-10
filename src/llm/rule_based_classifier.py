from dataclasses import dataclass

from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


# noch nicht kalibriert, erstmal plausibel geschätzt
SUSTAINED_STREAK_HOURS = 24.0
MULTI_SCALE_MINIMUM = 2


@dataclass(frozen=True)
class RuleClassificationResult:
    classification: Classification
    reasoning: str


def rule_based_classify(
    state: StructuredState
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

    scale_streak_hours = anomaly["scale_streak_hours"]

    sustained_scales = [
        scale
        for scale in anomaly["available_scales"]
        if (streak := scale_streak_hours[scale]) is not None and streak >= SUSTAINED_STREAK_HOURS
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
                f"strong, sustained downward deviation on scale '{dominant_scale}' ({scale_streak_hours[dominant_scale]:.0f}h >= {SUSTAINED_STREAK_HOURS:.0f}h)."
            ),
        )

    if len(sustained_scales) >= MULTI_SCALE_MINIMUM:
        return RuleClassificationResult(
            classification="new_pattern",
            reasoning=f"sustained deviation across multiple scales at once ({', '.join(sustained_scales)}).",
        )

    return RuleClassificationResult(
        classification="peak",
        reasoning=f"unusual ({anomaly['level']}), but no sustained absence or multi-scale signature.",
    )


