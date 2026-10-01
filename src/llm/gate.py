from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState


def gate_classification(state: StructuredState) -> Classification | None:
    # None = Gate offen, dann entscheidet Regel oder LLM
    anomaly = state["anomaly"]

    if state["observation"]["value_implausible"]:
        # level ist an so einem Tag leer ->vor der unknown-Prüfung offen lassen
        return None

    if anomaly["sustained_drift"]:
        return None

    if anomaly["level"] is None:
        return "unknown"

    if anomaly["level"] == "normal":
        return "normal"

    return None
