from dataclasses import dataclass

from src.common.sample_structured_state import valid_structured_state
from src.llm.llm_schema import Classification
from src.numerical_analysis.anomaly_detection import resolve_dominant_scale
from src.structured_state.structured_state_schema import AnomalyLevel, SCALE_NAMES, StructuredState


@dataclass(frozen=True)
class LLMEvaluationCase:
    case_id: str
    expected_classification: Classification
    reasoning: str
    state: StructuredState


_BASE_EVENT = {
    "end": "2015-12-22T00:00:00+00:00",
    "event_id": "vacation-2015-12",
    "event_type": "absence",
    "known_at": "2015-11-15T00:00:00+00:00",
    "start": "2015-12-15T00:00:00+00:00",
}

_PEAK_TIMESTAMP = "2015-12-15T10:00:00+00:00"


def _anomaly_block(
    *,
    scores: dict[str, float],
    level: AnomalyLevel,
    streak_days: dict[str, float],
) -> dict[str, object]:
    dominant_scale, score, direction = resolve_dominant_scale(scores)

    return {
        "score": score,
        "level": level,
        "direction": direction,
        "dominant_scale": dominant_scale,
        "peak_timestamp": _PEAK_TIMESTAMP,
        "scale_scores": {scale: scores.get(scale) for scale in SCALE_NAMES},
        "scale_anomaly_streak_days": {scale: streak_days.get(scale) if scale in scores else None for scale in SCALE_NAMES},
        "available_scales": [scale for scale in SCALE_NAMES if scale in scores],
    }


def _context_block(*, source_available: bool, with_event: bool) -> dict[str, object]:
    return {
        "events": [_BASE_EVENT] if with_event else [],
        "retrieved_at": "2015-12-15T11:00:00+00:00",
        "source": "simulated_calendar",
        "source_available": source_available,
        "window_end": "2015-12-16T11:00:00+00:00",
        "window_start": "2015-12-14T11:00:00+00:00",
    }


def _case(
    *,
    case_id: str,
    expected: Classification,
    reasoning: str,
    current_power_w: float,
    value_implausible: bool,
    anomaly: dict[str, object],
    context: dict[str, object],
) -> LLMEvaluationCase:
    state = valid_structured_state()
    state["observation"]["current_power_w"] = current_power_w
    state["observation"]["value_implausible"] = value_implausible
    state["anomaly"] = anomaly  # type: ignore[typeddict-item]
    state["context"] = context  # type: ignore[typeddict-item]

    return LLMEvaluationCase(case_id=case_id, expected_classification=expected, reasoning=reasoning, state=state)


def build_evaluation_cases() -> tuple[LLMEvaluationCase, ...]:
    return (
        _case(
            case_id="normal",
            expected="normal",
            reasoning="Alle Skalen nur leicht erhöht, level normal, kein Event - kein Grund für eine Auffälligkeit.",
            current_power_w=360.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.4, "weekly": 0.3, "long_term": 0.2},
                level="normal",
                streak_days={"daily": 1.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="peak",
            expected="peak",
            reasoning="Starke, einzelne Abweichung nach oben, aber Streak nur 1 Tag - nicht sustained, also kein new_pattern.",
            current_power_w=1319.9,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 3.77, "weekly": 3.73, "long_term": 3.26},
                level="strong_anomaly",
                streak_days={"daily": 1.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="absence",
            expected="absence",
            reasoning="Starke, anhaltende Abweichung nach unten auf der dominanten Skala plus passendes Kalender-Event.",
            current_power_w=45.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": -3.7, "weekly": -1.2, "long_term": -1.0},
                level="strong_anomaly",
                streak_days={"daily": 5.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=True),
        ),
        _case(
            case_id="new_pattern",
            expected="new_pattern",
            reasoning="Abweichung nach oben, seit mehreren Tagen anhaltend auf einem Großteil der verfügbaren Skalen zugleich (multi_scale_minimum_ratio=0.5).",
            current_power_w=980.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 3.5, "weekly": 3.1, "long_term": 1.1},
                level="strong_anomaly",
                streak_days={"daily": 5.0, "weekly": 4.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="measurement_error",
            expected="measurement_error",
            reasoning="value_implausible=true bei sonst peak-artiger Signatur - Prompt verlangt measurement_error statt peak.",
            current_power_w=1319.9,
            value_implausible=True,
            anomaly=_anomaly_block(
                scores={"daily": 3.77, "weekly": 3.73, "long_term": 3.26},
                level="strong_anomaly",
                streak_days={"daily": 1.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="unknown",
            expected="unknown",
            reasoning=(
                "Nur eine Skala verfügbar, Abweichung nach unten aber Kalender nicht verfügbar (absence nicht "
                "belegbar), Streak zu kurz für new_pattern, direction low passt nicht zu peak - keine der "
                "anderen Klassen ist durch die Regeln gedeckt."
            ),
            current_power_w=180.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": -2.2},
                level="unusual",
                streak_days={"daily": 1.0},
            ),
            context=_context_block(source_available=False, with_event=False),
        ),
    )
