from __future__ import annotations

import re
from typing import Any

from experiments.prototypes.vertical_slice.llm_evaluation.evaluation_cases import (
    EvaluationCase,
)


def _parse_path(path: str) -> list[str | int]:
    """
    Convert:
        context.events[0].type

    into:
        ["context", "events", 0, "type"]
    """
    parts: list[str | int] = []

    for token in path.split("."):
        match = re.fullmatch(r"([^\[]+)(?:\[(\d+)\])?", token)

        if match is None:
            raise ValueError(f"Invalid field path: {path}")

        parts.append(match.group(1))

        if match.group(2) is not None:
            parts.append(int(match.group(2)))

    return parts


def resolve_path(
    data: dict[str, Any],
    path: str,
) -> Any:
    current: Any = data

    for part in _parse_path(path):
        if isinstance(part, int):
            if not isinstance(current, list):
                raise KeyError(path)
            current = current[part]

        else:
            if not isinstance(current, dict):
                raise KeyError(path)
            current = current[part]

    return current


def _all_evidence(
    output: dict[str, Any],
) -> list[dict[str, Any]]:
    return (
        output.get("numerical_evidence", [])
        + output.get("contextual_evidence", [])
    )


def _combined_text(
    output: dict[str, Any],
) -> str:
    parts = [
        str(output.get("explanation", "")),
    ]

    for item in _all_evidence(output):
        parts.append(str(item.get("relevance", "")))

    for item in output.get("limitations", []):
        parts.append(str(item))

    for item in output.get("hypotheses", []):
        parts.append(str(item))

    return " ".join(parts).lower()


def evidence_path_accuracy(
    state: dict[str, Any],
    output: dict[str, Any],
) -> float:
    evidence = _all_evidence(output)

    if not evidence:
        return 1.0

    correct = 0

    for item in evidence:
        path = item.get("field")

        if not isinstance(path, str):
            continue

        try:
            resolve_path(state, path)
            correct += 1
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    return correct / len(evidence)


def evidence_value_accuracy(
    state: dict[str, Any],
    output: dict[str, Any],
) -> float:
    evidence = _all_evidence(output)

    if not evidence:
        return 1.0

    correct = 0

    for item in evidence:
        path = item.get("field")

        if not isinstance(path, str):
            continue

        try:
            actual_value = resolve_path(state, path)
        except (KeyError, IndexError, TypeError, ValueError):
            continue

        if actual_value == item.get("value"):
            correct += 1

    return correct / len(evidence)


def required_evidence_recall(
    case: EvaluationCase,
    output: dict[str, Any],
) -> float:
    required = set(case.required_evidence_paths)

    if not required:
        return 1.0

    supplied = {
        item.get("field")
        for item in _all_evidence(output)
        if isinstance(item.get("field"), str)
    }

    return len(required & supplied) / len(required)


def forbidden_evidence_used(
    case: EvaluationCase,
    output: dict[str, Any],
) -> bool:
    forbidden = set(case.forbidden_evidence_paths)

    if not forbidden:
        return False

    supplied = {
        item.get("field")
        for item in _all_evidence(output)
        if isinstance(item.get("field"), str)
    }

    return bool(forbidden & supplied)


_CURRENT_EXPECTED_PATTERNS = [
    r"current (?:power|consumption).*within .*expected",
    r"current (?:power|consumption).*close to .*expected",
    r"current (?:power|consumption).*aligned with .*expected",
    r"current (?:power|consumption).*consistent with .*expected",
    r"current .*within expected limits",
    r"current .*within the expected range",
    r"current .*typical",
]

_SCALAR_COMPARISON_PATTERNS = [
    r"current .* lower than .*mean",
    r"current .* higher than .*mean",
    r"current .* below .*mean",
    r"current .* above .*mean",
    r"current .* compared (?:with|to)",
]


def has_forbidden_scalar_comparison(
    output: dict[str, Any],
) -> bool:
    text = _combined_text(output)

    patterns = (
        _CURRENT_EXPECTED_PATTERNS
        + _SCALAR_COMPARISON_PATTERNS
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


_FORECAST_LEAKAGE_PATTERNS = [
    r"current .*forecast",
    r"current .*prediction interval",
    r"current .*forecast interval",
    r"current .*minimum .*forecast",
    r"current .*maximum .*forecast",
    r"current .*forecast mean",
    r"current .*forecast peak",
    r"current .*falls within .*forecast",
    r"current .*close to .*forecast",
    r"current .*aligned with .*forecast",
]


def has_forecast_leakage(
    output: dict[str, Any],
) -> bool:
    text = _combined_text(output)

    return any(
        re.search(pattern, text)
        for pattern in _FORECAST_LEAKAGE_PATTERNS
    )


def context_handling_ok(
    case: EvaluationCase,
    output: dict[str, Any],
) -> bool:
    state = case.structured_state
    text = _combined_text(output)

    calendar_available = (
        state
        .get("context", {})
        .get("calendar_available")
    )

    currently_absent = (
        state
        .get("context", {})
        .get("currently_absent")
    )

    # Calendar available -> model must not claim it is unavailable.
    if calendar_available is True:
        if (
            "calendar context is unavailable" in text
            or "calendar is unavailable" in text
        ):
            return False

    # Calendar unavailable -> model must not infer that no events
    # or absence exist.
    if calendar_available is False:
        forbidden_claims = [
            "no calendar events",
            "no events are present",
            "no contextual evidence",
            "absence of contextual evidence",
            "there is no evidence of absence",
            "no evidence of absence",
        ]

        if any(claim in text for claim in forbidden_claims):
            return False

    # Explicit active absence must produce absence.
    if currently_absent is True:
        if output.get("classification") != "absence":
            return False

    return True


def has_unsupported_claim(
    case: EvaluationCase,
    output: dict[str, Any],
) -> bool:
    """
    Conservative deterministic proxy.

    Only catches claims that can clearly be contradicted by the
    structured state or by explicit prompt rules.
    """
    state = case.structured_state
    text = _combined_text(output)

    calendar_available = (
        state
        .get("context", {})
        .get("calendar_available")
    )

    if (
        calendar_available is True
        and "calendar context is unavailable" in text
    ):
        return True

    if (
        calendar_available is False
        and (
            "no calendar events" in text
            or "no events are present" in text
            or "no evidence of absence" in text
        )
    ):
        return True

    if has_forecast_leakage(output):
        return True

    if has_forbidden_scalar_comparison(output):
        return True

    return False


def evaluate_output(
    case: EvaluationCase,
    *,
    status: str,
    output: dict[str, Any] | None,
) -> dict[str, Any]:
    if status != "success" or output is None:
        return {
            "case": case.name,
            "expected_classification": case.expected_classification,
            "predicted_classification": None,

            "valid_output": False,
            "classification_correct": False,

            "evidence_path_accuracy": 0.0,
            "evidence_value_accuracy": 0.0,
            "required_evidence_recall": 0.0,

            "forbidden_evidence_used": False,
            "forbidden_comparison": False,
            "unsupported_claim": False,
            "context_handling_ok": False,
            "forecast_leakage": False,
        }

    return {
        "case": case.name,
        "expected_classification": case.expected_classification,
        "predicted_classification": output.get("classification"),

        "valid_output": True,

        "classification_correct": (
            output.get("classification")
            == case.expected_classification
        ),

        "evidence_path_accuracy": evidence_path_accuracy(
            case.structured_state,
            output,
        ),

        "evidence_value_accuracy": evidence_value_accuracy(
            case.structured_state,
            output,
        ),

        "required_evidence_recall": required_evidence_recall(
            case,
            output,
        ),

        "forbidden_evidence_used": forbidden_evidence_used(
            case,
            output,
        ),

        "forbidden_comparison": has_forbidden_scalar_comparison(
            output,
        ),

        "unsupported_claim": has_unsupported_claim(
            case,
            output,
        ),

        "context_handling_ok": context_handling_ok(
            case,
            output,
        ),

        "forecast_leakage": has_forecast_leakage(
            output,
        ),
    }