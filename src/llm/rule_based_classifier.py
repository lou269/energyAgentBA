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
    sustained_daily_elevated_hours: float,
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

    scale_elevated_hours = anomaly["scale_elevated_hours"]

    sustained_scales = [
        scale
        for scale in anomaly["available_scales"]
        if (elevated_hours := scale_elevated_hours[scale]) is not None and elevated_hours >= sustained_daily_elevated_hours
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
                f"strong, sustained downward deviation on scale '{dominant_scale}' ({scale_elevated_hours[dominant_scale]:.0f}h elevated today >= {sustained_daily_elevated_hours:.0f}h)."
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


