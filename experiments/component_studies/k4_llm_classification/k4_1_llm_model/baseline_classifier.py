from src.llm.llm_schema import Classification
from src.llm.rule_based_classifier import rule_based_classify
from src.structured_state.structured_state_schema import StructuredState


def baseline_classify(
    state: StructuredState,
    *,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
    local_timezone: str,
) -> Classification:

    if state["anomaly"]["level"] == "normal":
        return "normal"


    return rule_based_classify(
        state,
        sustained_anomaly_streak_days=sustained_anomaly_streak_days,
        min_sustained_scales=min_sustained_scales,
        local_timezone=local_timezone,
    ).classification


