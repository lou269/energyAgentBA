import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.k2_llm.k2_config import BASELINE_ID, LLMModelVariant
from src.common.sample_structured_state import valid_structured_state
from src.common.timestamps import local_date_text, local_midnight_utc
from src.config.config_forecasting import LLMConfig, NumericalAnalysisConfig
from src.llm.client import LLMClient, OllamaClient
from src.llm.gate import gate_classification
from src.llm.inference import LLMAttemptRecord, LLMInferenceError, infer_llm_output
from src.llm.llm_schema import Classification
from src.llm.rule_based_classifier import rule_based_classify
from src.numerical_analysis.daily_analysis import level_shift_thresholds
from src.pipeline.io import append_csv, append_jsonl
from src.structured_state.structured_state_schema import (
    DEVIATION_SCALE_NAMES,
    LEVEL_SHIFT_SCALE_NAMES,
    SCALE_NAMES,
    StructuredState,
)

logger = logging.getLogger(__name__)

# die Fälle sollen so aussehen, wie build_anomaly_detection sie mit der Pipeline-Konfiguration baut
ANALYSIS_CONFIG = NumericalAnalysisConfig()

# der analysierte Tag aller Fälle, wie in valid_structured_state
ANALYZED_DAY = "2015-12-15"

# Urlaub seit einer Woche, deckt den eingeordneten Tag (15.12.) aus valid_structured_state ab
_ABSENCE_EVENT = {
    "end": "2015-12-22T00:00:00+00:00",
    "event_id": "vacation-2015-12",
    "known_at": "2015-11-15T00:00:00+00:00",
    "start": "2015-12-08T00:00:00+00:00",
    "title": "Urlaub",
}


@dataclass(frozen=True)
class LLMEvaluationCase:
    case_id: str
    expected_classification: Classification
    reasoning: str
    state: StructuredState
    reaches_llm: bool


def _exceeding_since(
    streak: float | None, value: float | None, threshold: float
) -> str | None:
    # Beginn des Verlaufs: nur wenn die Skala heute über ihrer Streak-Schwelle liegt, sonst leer
    if streak is None or streak < 1 or value is None or abs(value) < threshold:
        return None

    start = local_midnight_utc(
        ANALYZED_DAY, LOCAL_TIMEZONE, days_offset=1 - int(streak)
    )

    return local_date_text(start, LOCAL_TIMEZONE)


def _anomaly_block(
    *,
    scores: dict[str, float],
    direction: str,
    streak_days: dict[str, float],
    deviation_pct: dict[str, float],
) -> dict[str, object]:
    # alarm_scales wie in build_anomaly_detection: jede Gate-Skala gegen ihre Schwelle, eine genügt für level
    alarm_scales = [
        scale
        for scale in ANALYSIS_CONFIG.single_day_scales
        if scale in scores and abs(scores[scale]) >= ANALYSIS_CONFIG.unusual_threshold
    ]
    deviation_block = {
        scale: deviation_pct.get(scale) for scale in DEVIATION_SCALE_NAMES
    }
    # verfügbar heißt: Score da, bei long_term die Prozentabweichung
    available = [
        scale
        for scale in SCALE_NAMES
        if (
            deviation_pct.get("long_term") is not None
            if scale == "long_term"
            else scale in scores
        )
    ]
    level_values = {
        "weekly": scores.get("weekly"),
        "long_term": deviation_pct.get("long_term"),
    }
    thresholds = level_shift_thresholds(ANALYSIS_CONFIG)

    # Streak und Beginn gibt es nur für die Niveau-Skalen
    streak_block = {
        scale: (
            streak_days.get(scale)
            if scale in ANALYSIS_CONFIG.level_shift_scales and scale in available
            else None
        )
        for scale in LEVEL_SHIFT_SCALE_NAMES
    }
    since_block = {
        scale: (
            _exceeding_since(
                streak_block[scale], level_values[scale], thresholds[scale]
            )
            if scale in ANALYSIS_CONFIG.level_shift_scales
            else None
        )
        for scale in LEVEL_SHIFT_SCALE_NAMES
    }
    sustained_scales = [
        scale
        for scale in LEVEL_SHIFT_SCALE_NAMES
        if (streak_block[scale] or 0.0) >= ANALYSIS_CONFIG.sustained_anomaly_streak_days
    ]

    return {
        "level": "unusual" if alarm_scales else "normal",
        "direction": direction,
        "alarm_scales": alarm_scales,
        "scale_anomaly_streak_days": streak_block,
        "scale_exceeding_since": since_block,
        "scale_deviation_pct": deviation_block,
        "sustained_scales": sustained_scales,
        "sustained_drift": len(sustained_scales)
        >= ANALYSIS_CONFIG.min_sustained_scales,
        "available_scales": available,
    }


def _empty_anomaly_block() -> dict[str, object]:
    return {
        "level": None,
        "direction": None,
        "alarm_scales": [],
        "scale_anomaly_streak_days": {scale: None for scale in LEVEL_SHIFT_SCALE_NAMES},
        "scale_exceeding_since": {scale: None for scale in LEVEL_SHIFT_SCALE_NAMES},
        "scale_deviation_pct": {scale: None for scale in DEVIATION_SCALE_NAMES},
        "sustained_scales": [],
        "sustained_drift": False,
        "available_scales": [],
    }


def _context_block(
    *, source_available: bool, with_event: bool = False
) -> dict[str, object]:
    return {
        "events": [_ABSENCE_EVENT] if with_event else [],
        "retrieved_at": "2015-12-16T00:00:00+00:00",
        "source": "simulated_calendar",
        "source_available": source_available,
        "window_end": "2015-12-17T00:00:00+00:00",
        "window_start": "2015-12-15T00:00:00+00:00",
    }


def _case(
    *,
    case_id: str,
    expected: Classification,
    reasoning: str,
    value_implausible: bool,
    anomaly: dict[str, object],
    context: dict[str, object],
) -> LLMEvaluationCase:
    state = valid_structured_state()
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
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.4, "weekday": 0.5, "weekly": 0.3},
                direction="high",
                streak_days={"weekly": 1.0, "long_term": 1.0},
                deviation_pct={"weekday": 6.0, "weekly": 4.0, "long_term": 2.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="peak",
            expected="peak",
            reasoning="Starke, einzelne Abweichung nach oben, aber Streak nur 1 Tag -> nicht sustained, also kein new_pattern.",
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 1.1, "weekday": 3.77, "weekly": 1.4},
                direction="high",
                streak_days={"weekly": 1.0, "long_term": 1.0},
                deviation_pct={"weekday": 45.0, "weekly": 12.0, "long_term": 6.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="new_pattern",
            expected="new_pattern",
            reasoning=(
                "Abweichung nach oben, beide Niveau-Skalen (weekly, long_term) seit mindestens sustained_anomaly_streak_days=6 Tagen anhaltend "
                "(min_sustained_scales=2) -> new_pattern."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.9, "weekday": 3.5, "weekly": 3.1},
                direction="high",
                streak_days={"weekly": 7.0, "long_term": 7.0},
                deviation_pct={"weekday": 38.0, "weekly": 36.0, "long_term": 22.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="low_single_scale",
            expected="low",
            reasoning=(
                "Nur weekday verfügbar, Abweichung nach unten, Streak zu kurz für new_pattern, Kalender nicht verfügbar (absence nicht belegbar) -> low."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"weekday": -3.4},
                direction="low",
                streak_days={},
                deviation_pct={"weekday": -30.0},
            ),
            context=_context_block(source_available=False),
        ),
        _case(
            case_id="peak_single_sustained_scale",
            expected="peak",
            reasoning=(
                "Einzeltag-Alarm nach oben, dazu ist nur weekly sustained (Streak=6), "
                "min_sustained_scales=2 verlangt aber beide Niveau-Skalen - bleibt peak trotz langer Einzel-Skalen-Streak."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 1.0, "weekday": 3.5, "weekly": 1.6},
                direction="high",
                streak_days={"weekly": 6.0, "long_term": 1.0},
                deviation_pct={"weekday": 40.0, "weekly": 12.0, "long_term": 4.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="normal_single_sustained_scale",
            expected="normal",
            reasoning=(
                "Nur weekly ist seit 6 Tagen leicht erhöht, kein Einzeltag-Alarm (level normal), eine Skala genügt nicht für new_pattern "
                "(min_sustained_scales=2). Seit dem Gate mit einer Skala erreicht der Tag das LLM."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.5, "weekday": 0.9, "weekly": 1.4},
                direction="high",
                streak_days={"weekly": 6.0, "long_term": 1.0},
                deviation_pct={"weekday": 7.0, "weekly": 9.0, "long_term": 3.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="normal_weekly_after_reset",
            expected="normal",
            reasoning=(
                "Wie in Wochen nach einem Reset: long_term ohne Wert, nur weekly seit 7 Tagen erhöht, der Tag selbst etwas niedriger "
                "(direction=low). Ohne long_term kein sustained_drift -> normal, die Woche liegt höher, nicht niedriger."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.5, "weekday": -0.9, "weekly": 2.0},
                direction="low",
                streak_days={"weekly": 7.0},
                deviation_pct={"weekday": -10.0, "weekly": 32.0},
            ),
            context=_context_block(source_available=False),
        ),
        _case(
            case_id="new_pattern_at_min_scales_boundary",
            expected="new_pattern",
            reasoning=(
                "Genau an der Streak-Grenze: weekly und long_term je sustained_anomaly_streak_days=6 von 7 Tagen, "
                "beide Niveau-Skalen sustained (min_sustained_scales=2) - reicht für new_pattern."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.8, "weekday": 3.2, "weekly": 3.0},
                direction="high",
                streak_days={"weekly": 6.0, "long_term": 6.0},
                deviation_pct={"weekday": 35.0, "weekly": 30.0, "long_term": 16.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="measurement_error_missing_day",
            expected="measurement_error",
            reasoning=(
                "Tag komplett ausgefallen: value_implausible=true, alle Anomalie-Felder leer. Außer dem Flag ist nichts zu lesen."
            ),
            value_implausible=True,
            anomaly=_empty_anomaly_block(),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="new_pattern_drift_down",
            expected="new_pattern",
            reasoning=(
                "weekly und long_term seit Tagen deutlich niedriger, der Tag selbst leicht höher (direction=high). "
                "Die Erklärung muss von weniger Verbrauch sprechen, die Richtung der Änderung steht in scale_deviation_pct."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.6, "weekday": 0.8, "weekly": -3.2},
                direction="high",
                streak_days={"weekly": 7.0, "long_term": 6.0},
                deviation_pct={"weekday": 8.0, "weekly": -40.0, "long_term": -25.0},
            ),
            context=_context_block(source_available=True),
        ),
        _case(
            case_id="absence_drift_down",
            expected="absence",
            reasoning=(
                "Wie new_pattern_drift_down, dazu ein Urlaub, der den Tag abdeckt. Die Rückgänge in scale_deviation_pct "
                "machen die Ausnahme in Schritt 2 greifbar, obwohl direction=high ist."
            ),
            value_implausible=False,
            anomaly=_anomaly_block(
                scores={"daily": 0.6, "weekday": 0.8, "weekly": -3.2},
                direction="high",
                streak_days={"weekly": 7.0, "long_term": 6.0},
                deviation_pct={"weekday": 8.0, "weekly": -40.0, "long_term": -25.0},
            ),
            context=_context_block(source_available=True, with_event=True),
        ),
    )

    return tuple(case for case in cases if case.reaches_llm)


# was der Prompt je Klasse zu zitieren verlangt
_SINGLE_DAY_PATHS = frozenset({"anomaly.level", "anomaly.direction"})
_DRIFT_PATHS = frozenset(
    {
        "anomaly.sustained_drift",
        "anomaly.scale_anomaly_streak_days.weekly",
        "anomaly.scale_anomaly_streak_days.long_term",
    }
)

EXPECTED_EVIDENCE_PATHS: dict[str, frozenset[str]] = {
    "normal": frozenset({"anomaly.level"}),
    "peak": _SINGLE_DAY_PATHS,
    "new_pattern": _DRIFT_PATHS,
    "normal_single_sustained_scale": frozenset(
        {"anomaly.level", "anomaly.scale_anomaly_streak_days.weekly"}
    ),
    "normal_weekly_after_reset": frozenset(
        {"anomaly.level", "anomaly.scale_anomaly_streak_days.weekly"}
    ),
    "low_single_scale": _SINGLE_DAY_PATHS,
    "peak_single_sustained_scale": _SINGLE_DAY_PATHS,
    "new_pattern_at_min_scales_boundary": _DRIFT_PATHS,
    "measurement_error_missing_day": frozenset({"observation.value_implausible"}),
    "new_pattern_drift_down": _DRIFT_PATHS,
    "absence_drift_down": frozenset(
        {
            "anomaly.level",
            "context.events.0.title",
        }
    ),
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
                case.state,
                local_timezone=LOCAL_TIMEZONE,
                min_sustained_scales=ANALYSIS_CONFIG.min_sustained_scales,
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
            "state": case.state,
        },
        raw_dir / f"{variant.model_id}.jsonl",
    )
