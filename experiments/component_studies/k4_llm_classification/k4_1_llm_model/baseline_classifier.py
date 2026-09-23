from src.llm.gate import gate_classification
from src.llm.llm_schema import Classification
from src.llm.rule_based_classifier import rule_based_classify
from src.structured_state.structured_state_schema import StructuredState


def baseline_classify(
    state: StructuredState,
    *,
    local_timezone: str,
) -> Classification:
    classification = gate_classification(state)
    if classification is not None:
        return classification

    return rule_based_classify(state, local_timezone=local_timezone).classification
