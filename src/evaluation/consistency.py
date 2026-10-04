import re
from collections.abc import Collection

from src.llm.llm_schema import Classification
from src.structured_state.structured_state_schema import StructuredState

EVENT_TYPE_PATH = re.compile(r"context\.events\.(\d+)\.event_type")


def missing_evidence_paths(
    classification: Classification,
    cited_paths: Collection[str],
    state: StructuredState,
) -> tuple[str, ...]:
    if classification in ("normal", "unknown"):
        return ()

    anomaly = state["anomaly"]

    if classification == "measurement_error":
        required = {"observation.value_implausible"}
    elif classification == "new_pattern":
        required = {"anomaly.sustained_drift"} | {
            f"anomaly.scale_anomaly_streak_days.{scale}"
            for scale in anomaly["sustained_scales"]
        }
    else:
        required = {"anomaly.level"}

    if classification in ("peak", "low"):
        required.add("anomaly.direction")

    missing = sorted(required - set(cited_paths))

    if classification == "absence" and not _cites_absence_event(cited_paths, state):
        missing.append("context.events.<index>.event_type")

    return tuple(missing)


def _cites_absence_event(cited_paths: Collection[str], state: StructuredState) -> bool:
    events = state["context"]["events"]

    for path in cited_paths:
        match = EVENT_TYPE_PATH.fullmatch(path)
        if match and int(match.group(1)) < len(events):
            if events[int(match.group(1))]["event_type"] == "absence":
                return True

    return False
