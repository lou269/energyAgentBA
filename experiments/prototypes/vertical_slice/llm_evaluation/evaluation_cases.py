from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    expected_classification: str
    structured_state: dict[str, Any]
    required_evidence_paths: tuple[str, ...] = ()
    forbidden_evidence_paths: tuple[str, ...] = ()


def _set_nested(
    state: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    parts = path.split(".")
    current = state

    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value


def _build_case(
    base_state: dict[str, Any],
    *,
    name: str,
    expected_classification: str,
    updates: dict[str, Any] | None = None,
    required_evidence_paths: tuple[str, ...] = (),
    forbidden_evidence_paths: tuple[str, ...] = (),
) -> EvaluationCase:
    state = deepcopy(base_state)

    for path, value in (updates or {}).items():
        _set_nested(state, path, value)

    return EvaluationCase(
        name=name,
        expected_classification=expected_classification,
        structured_state=state,
        required_evidence_paths=required_evidence_paths,
        forbidden_evidence_paths=forbidden_evidence_paths,
    )


def build_evaluation_cases(
    base_state: dict[str, Any],
) -> list[EvaluationCase]:
    """
    Build deterministic LLM interpretation test cases.

    The base state should come from the real vertical-slice pipeline.
    Numeric values, forecast values and timestamp therefore remain
    realistic while only explicitly controlled interpretation signals
    are changed.
    """

    cases: list[EvaluationCase] = []

    # ------------------------------------------------------------------
    # NORMAL
    # ------------------------------------------------------------------

    cases.append(
        _build_case(
            base_state,
            name="normal_calendar_available",
            expected_classification="normal",
            updates={
                "anomaly.level": "normal",
                "context.calendar_available": True,
                "context.currently_absent": False,
                "context.events": [],
            },
            required_evidence_paths=(
                "anomaly.level",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="normal_no_calendar",
            expected_classification="normal",
            updates={
                "anomaly.level": "normal",
                "context.calendar_available": False,
                "context.currently_absent": None,
                "context.events": [],
            },
            required_evidence_paths=(
                "anomaly.level",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="normal_low_direction",
            expected_classification="normal",
            updates={
                "anomaly.level": "normal",
                "anomaly.direction": "low",
                "context.calendar_available": True,
                "context.currently_absent": False,
                "context.events": [],
            },
            required_evidence_paths=(
                "anomaly.level",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="normal_high_direction",
            expected_classification="normal",
            updates={
                "anomaly.level": "normal",
                "anomaly.direction": "high",
                "context.calendar_available": True,
                "context.currently_absent": False,
                "context.events": [],
            },
            required_evidence_paths=(
                "anomaly.level",
            ),
        )
    )

    # ------------------------------------------------------------------
    # ABSENCE
    # ------------------------------------------------------------------

    vacation_event = [
        {
            "type": "absence",
            "label": "vacation",
            "start": "2013-09-14T23:00:00+00:00",
            "end": "2013-09-21T23:00:00+00:00",
        }
    ]

    cases.append(
        _build_case(
            base_state,
            name="absence_numerically_normal",
            expected_classification="absence",
            updates={
                "anomaly.level": "normal",
                "context.calendar_available": True,
                "context.currently_absent": True,
                "context.events": vacation_event,
            },
            required_evidence_paths=(
                "anomaly.level",
                "context.currently_absent",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="absence_unusual",
            expected_classification="absence",
            updates={
                "anomaly.level": "unusual",
                "context.calendar_available": True,
                "context.currently_absent": True,
                "context.events": vacation_event,
            },
            required_evidence_paths=(
                "context.currently_absent",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="absence_strong_anomaly",
            expected_classification="absence",
            updates={
                "anomaly.level": "strong_anomaly",
                "context.calendar_available": True,
                "context.currently_absent": True,
                "context.events": vacation_event,
            },
            required_evidence_paths=(
                "context.currently_absent",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="absence_without_event_details",
            expected_classification="absence",
            updates={
                "anomaly.level": "normal",
                "context.calendar_available": True,
                "context.currently_absent": True,
                "context.events": [],
            },
            required_evidence_paths=(
                "anomaly.level",
                "context.currently_absent",
            ),
        )
    )

    # ------------------------------------------------------------------
    # TEMPORARY PEAK
    #
    # These explicit fields represent upstream numerical analysis.
    # The LLM must not derive temporariness itself.
    # ------------------------------------------------------------------

    cases.append(
        _build_case(
            base_state,
            name="temporary_peak_explicit",
            expected_classification="temporary_peak",
            updates={
                "anomaly.level": "strong_anomaly",
                "anomaly.direction": "high",
                "analysis.temporary_deviation_detected": True,
                "analysis.deviation_persistence": "short_lived",
                "context.calendar_available": True,
                "context.currently_absent": False,
            },
            required_evidence_paths=(
                "analysis.temporary_deviation_detected",
                "analysis.deviation_persistence",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="temporary_peak_unusual",
            expected_classification="temporary_peak",
            updates={
                "anomaly.level": "unusual",
                "anomaly.direction": "high",
                "analysis.temporary_deviation_detected": True,
                "analysis.deviation_persistence": "short_lived",
            },
            required_evidence_paths=(
                "analysis.temporary_deviation_detected",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="high_without_temporary_evidence",
            expected_classification="unknown",
            updates={
                "anomaly.level": "strong_anomaly",
                "anomaly.direction": "high",
                "analysis.temporary_deviation_detected": False,
                "analysis.deviation_persistence": "unknown",
            },
            forbidden_evidence_paths=(
                "forecast.summary.peak_forecast_w",
            ),
        )
    )

    # ------------------------------------------------------------------
    # NEW PATTERN
    # ------------------------------------------------------------------

    cases.append(
        _build_case(
            base_state,
            name="new_pattern_persistent_shift",
            expected_classification="new_pattern",
            updates={
                "anomaly.level": "unusual",
                "analysis.persistent_shift_detected": True,
                "analysis.shift_type": "non_seasonal",
                "analysis.change_point_confirmed": True,
            },
            required_evidence_paths=(
                "analysis.persistent_shift_detected",
                "analysis.shift_type",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="new_pattern_confirmed_change_point",
            expected_classification="new_pattern",
            updates={
                "anomaly.level": "strong_anomaly",
                "analysis.persistent_shift_detected": True,
                "analysis.shift_type": "non_seasonal",
                "analysis.change_point_confirmed": True,
            },
            required_evidence_paths=(
                "analysis.persistent_shift_detected",
                "analysis.change_point_confirmed",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="new_pattern_normal_anomaly_level",
            expected_classification="new_pattern",
            updates={
                "anomaly.level": "normal",
                "analysis.persistent_shift_detected": True,
                "analysis.shift_type": "non_seasonal",
                "analysis.change_point_confirmed": True,
            },
            required_evidence_paths=(
                "analysis.persistent_shift_detected",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="shift_without_persistence",
            expected_classification="unknown",
            updates={
                "anomaly.level": "unusual",
                "analysis.persistent_shift_detected": False,
                "analysis.shift_type": "unknown",
                "analysis.change_point_confirmed": False,
            },
        )
    )

    # ------------------------------------------------------------------
    # SEASONAL CHANGE
    # ------------------------------------------------------------------

    cases.append(
        _build_case(
            base_state,
            name="seasonal_change_explicit",
            expected_classification="seasonal_change",
            updates={
                "anomaly.level": "unusual",
                "analysis.seasonal_change_detected": True,
                "analysis.seasonal_change_persistent": True,
            },
            required_evidence_paths=(
                "analysis.seasonal_change_detected",
                "analysis.seasonal_change_persistent",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="seasonal_change_strong_anomaly",
            expected_classification="seasonal_change",
            updates={
                "anomaly.level": "strong_anomaly",
                "analysis.seasonal_change_detected": True,
                "analysis.seasonal_change_persistent": True,
            },
            required_evidence_paths=(
                "analysis.seasonal_change_detected",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="season_field_only",
            expected_classification="unknown",
            updates={
                "anomaly.level": "unusual",
                "analysis.seasonal_change_detected": False,
                "analysis.seasonal_change_persistent": False,
                "context.season": "autumn",
            },
        )
    )

    # ------------------------------------------------------------------
    # MEASUREMENT ISSUE
    # ------------------------------------------------------------------

    cases.append(
        _build_case(
            base_state,
            name="measurement_invalid",
            expected_classification="measurement_issue",
            updates={
                "measurement.valid": False,
                "measurement.issue": "invalid",
                "measurement.reliable": False,
            },
            required_evidence_paths=(
                "measurement.valid",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="measurement_missing",
            expected_classification="measurement_issue",
            updates={
                "measurement.valid": False,
                "measurement.issue": "missing",
                "measurement.reliable": False,
            },
            required_evidence_paths=(
                "measurement.issue",
            ),
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="measurement_unreliable",
            expected_classification="measurement_issue",
            updates={
                "measurement.valid": True,
                "measurement.issue": "unreliable",
                "measurement.reliable": False,
            },
            required_evidence_paths=(
                "measurement.reliable",
            ),
        )
    )

    # ------------------------------------------------------------------
    # UNKNOWN
    # ------------------------------------------------------------------

    cases.append(
        _build_case(
            base_state,
            name="unknown_unusual_only",
            expected_classification="unknown",
            updates={
                "anomaly.level": "unusual",
                "anomaly.direction": "low",
                "context.calendar_available": True,
                "context.currently_absent": False,
                "context.events": [],
            },
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="unknown_strong_anomaly_only",
            expected_classification="unknown",
            updates={
                "anomaly.level": "strong_anomaly",
                "anomaly.direction": "high",
                "context.calendar_available": True,
                "context.currently_absent": False,
                "context.events": [],
            },
        )
    )

    cases.append(
        _build_case(
            base_state,
            name="unknown_no_calendar_unusual",
            expected_classification="unknown",
            updates={
                "anomaly.level": "unusual",
                "context.calendar_available": False,
                "context.currently_absent": None,
                "context.events": [],
            },
        )
    )

    selected_case_names = {
        # normal
        "normal_calendar_available",
        "normal_no_calendar",

        # absence
        "absence_numerically_normal",
        "absence_strong_anomaly",

        # temporary_peak
        "temporary_peak_explicit",
        "temporary_peak_unusual",

        # new_pattern
        "new_pattern_persistent_shift",
        "new_pattern_normal_anomaly_level",

        # seasonal_change
        "seasonal_change_explicit",
        "seasonal_change_strong_anomaly",

        # measurement_issue
        "measurement_invalid",
        "measurement_unreliable",

        # unknown / boundary cases
        "high_without_temporary_evidence",
        "season_field_only",
    }

    return [
        case
        for case in cases
        if case.name in selected_case_names
    ]