import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.k4_llm.k4_config import BASELINE_ID, LLMModelVariant
from src.common.sample_structured_state import valid_structured_state
from src.config.config_forecasting import LLMConfig, NumericalAnalysisConfig
from src.llm.client import LLMClient, OllamaClient
from src.llm.gate import gate_classification
from src.llm.inference import LLMAttemptRecord, LLMInferenceError, infer_llm_output
from src.llm.llm_schema import Classification
from src.llm.rule_based_classifier import rule_based_classify
from src.pipeline.io import append_csv, append_jsonl
from src.structured_state.structured_state_schema import (
    AnomalyLevel,
    SCALE_NAMES,
    StructuredState,
)

logger = logging.getLogger(__name__)

# die Fälle sollen so aussehen, wie build_anomaly_detection sie mit der Pipeline-Konfiguration baut
ANALYSIS_CONFIG = NumericalAnalysisConfig()


@dataclass(frozen=True)
class LLMEvaluationCase:
    case_id: str
    expected_classification: Classification
    reasoning: str
    state: StructuredState
    reaches_llm: bool


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
    # wie in build_anomaly_detection: Score und Richtung nur aus den Gate-Skalen
    gate_scores = {
        scale: value
        for scale, value in scores.items()
        if scale in ANALYSIS_CONFIG.gate_scales
    }
    dominant_scale = max(gate_scores, key=lambda scale: abs(gate_scores[scale]))
    signed_score = gate_scores[dominant_scale]

    sustained_scales = [
        scale
        for scale in SCALE_NAMES
        if scale in scores
        and streak_days.get(scale, 0.0) >= ANALYSIS_CONFIG.sustained_anomaly_streak_days
    ]

    return {
        "score": abs(signed_score),
        "level": level,
        "direction": (
            "high" if signed_score > 0 else "low" if signed_score < 0 else None
        ),
        "dominant_scale": dominant_scale,
        "peak_timestamp": _PEAK_TIMESTAMP,
        "scale_scores": {scale: scores.get(scale) for scale in SCALE_NAMES},
        "scale_anomaly_streak_days": {
            scale: streak_days.get(scale) if scale in scores else None
            for scale in SCALE_NAMES
        },
        "sustained_scales": sustained_scales,
        "sustained_drift": len(sustained_scales)
        >= ANALYSIS_CONFIG.min_sustained_scales,
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

    reaches_llm = gate_classification(state) is None

    return LLMEvaluationCase(
        case_id=case_id,
        expected_classification=expected,
        reasoning=reasoning,
        state=state,
        reaches_llm=reaches_llm,
    )


def llm_relevant_cases() -> tuple[LLMEvaluationCase, ...]:
    # Alle Fälle, davon nur die, die das Gate an das LLM weitergibt
    cases = (
        _case(
            case_id="normal",
            expected="normal",
            reasoning="Alle Skalen nur leicht erhöht, level normal, kein Event -> kein Grund für eine Auffälligkeit.",
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
            reasoning="Starke, einzelne Abweichung nach oben, aber Streak nur 1 Tag -> nicht sustained, also kein new_pattern.",
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
            reasoning=(
                "Abweichung nach oben, auf 2 von 3 verfügbaren Skalen seit mehr als sustained_anomaly_streak_days=6 Tagen anhaltend"
                "(min_sustained_scales=2) -> new_pattern."
            ),
            current_power_w=980.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 3.5, "weekly": 3.1, "long_term": 1.1},
                level="strong_anomaly",
                streak_days={"daily": 8.0, "weekly": 7.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="measurement_error",
            expected="measurement_error",
            reasoning="value_implausible=true bei sonst peak-artiger Signatur -> Prompt verlangt measurement_error statt peak.",
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
            case_id="low_single_scale",
            expected="low",
            reasoning=(
                "Nur eine Skala verfügbar, Abweichung nach unten, Streak zu kurz für new_pattern, Kalender nicht verfügbar (absence nicht belegbar) -> low."
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
        _case(
            case_id="unknown_conflicting_scales",
            expected="unknown",
            reasoning=(
                "Zwei verfügbare Skalen widersprechen sich in der Richtung (daily stark positiv, weekly stark negativ), keine sustained "
                "-> keine der Regeln greift eindeutig, echte widersprüchliche Evidenz."
            ),
            current_power_w=700.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 3.0, "weekly": -3.2},
                level="strong_anomaly",
                streak_days={"daily": 1.0, "weekly": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="peak_single_sustained_scale",
            expected="peak",
            reasoning=(
                "Nur eine von drei verfügbaren Skalen ist sustained (Streak=6 auf daily), "
                "min_sustained_scales=2 verlangt aber mindestens zwei - bleibt peak trotz langer Einzel-Skalen-Streak."
            ),
            current_power_w=1150.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 3.5, "weekly": 1.5, "long_term": 1.0},
                level="strong_anomaly",
                streak_days={"daily": 6.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="new_pattern_at_min_scales_boundary",
            expected="new_pattern",
            reasoning=(
                "Exakt an der min_sustained_scales-Schwelle: genau 2 von 3 Skalen sustained "
                "(daily+weekly), long_term nicht - reicht für new_pattern."
            ),
            current_power_w=950.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 3.2, "weekly": 3.0, "long_term": 1.2},
                level="strong_anomaly",
                streak_days={"daily": 6.0, "weekly": 6.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="absence_without_event",
            expected="low",
            reasoning=(
                "Absence-artige Signatur (starker Rückgang auf der dominanten Skala, aber nicht sustained genug für new_pattern), "
                "Kalender ist verfügbar aber ohne passendes Event - ohne Beleg keine absence -> low"
            ),
            current_power_w=48.0,
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": -3.7, "weekly": -1.2, "long_term": -1.0},
                level="strong_anomaly",
                streak_days={"daily": 5.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
        _case(
            case_id="measurement_error_weak_anomaly",
            expected="measurement_error",
            reasoning=(
                "value_implausible bei nur unusual (nicht strong_anomaly) Signatur, value_implausible muss auch bei schwacher Anomalie Vorrang vor der Anomalie-Stärke haben."
            ),
            current_power_w=620.0,
            value_implausible=True,
            anomaly=_anomaly_block(
                scores={"daily": 2.1, "weekly": 1.8, "long_term": 1.5},
                level="unusual",
                streak_days={"daily": 1.0, "weekly": 1.0, "long_term": 1.0},
            ),
            context=_context_block(source_available=True, with_event=False),
        ),
    )

    return tuple(case for case in cases if case.reaches_llm)


EXPECTED_EVIDENCE_PATHS: dict[str, frozenset[str]] = {
    "normal": frozenset({"anomaly.level"}),
    "peak": frozenset(
        {"anomaly.scale_scores.daily", "anomaly.scale_anomaly_streak_days.daily"}
    ),
    "absence": frozenset({"anomaly.direction", "context.events.0.event_type"}),
    "new_pattern": frozenset(
        {
            "anomaly.scale_anomaly_streak_days.daily",
            "anomaly.scale_anomaly_streak_days.weekly",
        }
    ),
    "measurement_error": frozenset({"observation.value_implausible"}),
    "low_single_scale": frozenset({"anomaly.scale_scores.daily"}),
    "unknown_conflicting_scales": frozenset(
        {"anomaly.scale_scores.daily", "anomaly.scale_scores.weekly"}
    ),
    "peak_single_sustained_scale": frozenset(
        {"anomaly.scale_scores.daily", "anomaly.scale_anomaly_streak_days.daily"}
    ),
    "new_pattern_at_min_scales_boundary": frozenset(
        {
            "anomaly.scale_anomaly_streak_days.daily",
            "anomaly.scale_anomaly_streak_days.weekly",
        }
    ),
    "absence_without_event": frozenset(
        {"context.source_available", "anomaly.direction"}
    ),
    "measurement_error_weak_anomaly": frozenset({"observation.value_implausible"}),
}


def classify_cases_with_model(
    variant: LLMModelVariant,
    cases: tuple[LLMEvaluationCase, ...],
    prompt: str,
    results_file: Path,
    raw_dir: Path,
    *,
    llm_config: LLMConfig,
    repetitions: int,
) -> None:
    client: LLMClient = OllamaClient(timeout_seconds=llm_config.request_timeout_seconds)

    try:
        client.get_model_metadata(variant.model)
    except Exception as error:
        logger.error(
            "Could not reach Ollama for %s (%s): %s",
            variant.model_id,
            variant.model,
            error,
        )
        client.close()
        return

    try:
        for case in cases:
            for repetition in range(1, repetitions + 1):
                row = _classify_case(
                    client,
                    variant,
                    case,
                    repetition,
                    prompt,
                    raw_dir,
                    llm_config=llm_config,
                )
                append_csv(pd.DataFrame([row]), results_file)

                # request_failed = Verbindungsfehler -> Rest der Variante wird übersprungen, invalid_output betrifft nur diesen Versuch
                if row["error_kind"] == "request_failed":
                    logger.error(
                        "Aborting remaining cases for %s (%s) after a request failure.",
                        variant.model_id,
                        variant.model,
                    )
                    return
    finally:
        # Modell explizit entladen, bevor die nächste Variante drankommt
        try:
            client.unload_model(variant.model)
        except Exception as error:
            logger.warning(
                "Could not unload %s (%s) from Ollama: %s",
                variant.model_id,
                variant.model,
                error,
            )

        client.close()


def classify_cases_with_baseline(
    cases: tuple[LLMEvaluationCase, ...],
    results_file: Path,
) -> None:
    for case in cases:
        classification = gate_classification(case.state)
        if classification is None:
            classification = rule_based_classify(
                case.state, local_timezone=LOCAL_TIMEZONE
            ).classification

        row = {
            "model_id": BASELINE_ID,
            "model": "rule_based",
            "case_id": case.case_id,
            "expected_classification": case.expected_classification,
            "repetition": 1,
            "valid": True,
            "classification": classification,
            "correct": classification == case.expected_classification,
            "attempt_count": 1,
            "evidence_reference_count": None,
            "evidence_paths": None,
            "generation_seconds": 0.0,
            "error_kind": None,
            "error": None,
        }
        append_csv(pd.DataFrame([row]), results_file)


def _classify_case(
    client: LLMClient,
    variant: LLMModelVariant,
    case: LLMEvaluationCase,
    repetition: int,
    prompt: str,
    raw_dir: Path,
    *,
    llm_config: LLMConfig,
) -> dict[str, object]:
    row: dict[str, object] = {
        "model_id": variant.model_id,
        "model": variant.model,
        "case_id": case.case_id,
        "expected_classification": case.expected_classification,
        "repetition": repetition,
        "valid": False,
        "classification": None,
        "correct": False,
        "attempt_count": 0,
        "evidence_reference_count": None,
        "evidence_paths": None,
        "generation_seconds": 0.0,
        "error_kind": None,
        "error": None,
    }

    seed = (
        llm_config.seed
        if llm_config.seed is None
        else llm_config.seed + (repetition - 1)
    )

    try:
        result = infer_llm_output(
            case.state,
            client=client,
            prompt=prompt,
            model=variant.model,
            temperature=llm_config.temperature,
            presence_penalty=llm_config.presence_penalty,
            seed=seed,
            max_attempts=llm_config.max_attempts,
            num_predict=llm_config.num_predict,
            num_ctx=llm_config.num_ctx,
            think=llm_config.think,
            keep_alive=llm_config.keep_alive,
        )
    except LLMInferenceError as error:
        _save_raw_attempt(
            raw_dir,
            variant,
            case,
            repetition,
            attempts=error.attempts,
            output=None,
            error=str(error),
        )
        row["attempt_count"] = len(error.attempts)
        row["generation_seconds"] = sum(
            attempt.generation_seconds for attempt in error.attempts
        )
        row["error_kind"] = "invalid_output"
        row["error"] = str(error)
        return row
    except Exception as error:
        _save_raw_attempt(
            raw_dir,
            variant,
            case,
            repetition,
            attempts=(),
            output=None,
            error=str(error),
        )
        row["error_kind"] = "request_failed"
        row["error"] = str(error)
        return row

    evidence_paths = [
        reference["path"] for reference in result.output["evidence_references"]
    ]
    _save_raw_attempt(
        raw_dir,
        variant,
        case,
        repetition,
        attempts=result.attempts,
        output=dict(result.output),
        error=None,
    )

    row["valid"] = True
    row["classification"] = result.output["classification"]
    row["correct"] = result.output["classification"] == case.expected_classification
    row["attempt_count"] = len(result.attempts)
    row["evidence_reference_count"] = len(evidence_paths)
    row["evidence_paths"] = ";".join(evidence_paths)
    row["generation_seconds"] = sum(
        attempt.generation_seconds for attempt in result.attempts
    )
    return row


def _save_raw_attempt(
    raw_dir: Path,
    variant: LLMModelVariant,
    case: LLMEvaluationCase,
    repetition: int,
    *,
    attempts: tuple[LLMAttemptRecord, ...],
    output: dict[str, object] | None,
    error: str | None,
) -> None:
    # nicht Teil von results.csv, für manuelle Durchsicht von explanation/evidence_references (Schema prüft keine inhaltliche Qualität)
    append_jsonl(
        {
            "model": variant.model,
            "case_id": case.case_id,
            "repetition": repetition,
            "expected_classification": case.expected_classification,
            "attempts": [asdict(attempt) for attempt in attempts],
            "output": output,
            "error": error,
        },
        raw_dir / f"{variant.model_id}.jsonl",
    )
