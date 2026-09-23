from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


def gate_classification(state: StructuredState) -> Classification | None:
    # None = Gate offen, dann entscheidet Regel oder LLM
    anomaly = state["anomaly"]

    if state["observation"]["value_implausible"]:
        # today_mean fehlt komplett -> anomaly_score ist dadurch selbst auch NaN
        return "measurement_error"

    if anomaly["sustained_drift"]:
        return None

    if anomaly["level"] is None:
        return "unknown"

    if anomaly["level"] == "normal":
        return "normal"

    return None
