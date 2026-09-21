import copy
from typing import Any, cast

from src.common.sample_structured_state import valid_structured_state

__all__ = ["valid_structured_state", "valid_llm_output"]


# rohe Modellantwort, nur path, kein value
_BASE_OUTPUT = {
    "schema_version": "1.3",
    "classification": "peak",
    "explanation": "Der aktuelle Verbrauch liegt deutlich über dem täglichen Erwartungswert.",
    "evidence_references": [
        {"path": "observation.current_power_w"},
        {"path": "analysis.daily_std_expected"},
        {"path": "anomaly.level"},
    ],
    "user_recommendation": "Keine spezifische Aktion empfohlen.",
    "uncertainty": "Gering.",
}


def valid_llm_output() -> dict[str, Any]:
    return cast(dict[str, Any], copy.deepcopy(_BASE_OUTPUT))