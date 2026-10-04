# python -m pytest tests/unit/structured_state/test_structured_state.py -v
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.context.calendar_context import build_calendar_context
from src.context.calendar_schema import CalendarContext
from src.pipeline.io import save_json
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_schema import (
    StructuredState,
    validate_structured_state,
)


DECISION_TIME = pd.Timestamp("2013-09-02T00:00:00+00:00")


def _analysis_row() -> pd.Series:
    return pd.Series(
        {
            "timestamp": DECISION_TIME - pd.Timedelta(hours=1),
            "value_implausible": False,
            "weekday_deviation_pct": 14.3,
            "weekly_deviation_pct": None,
            "long_term_deviation_pct": 3.7,
            "daily_score": 2.0,
            "weekday_score": 1.8,
            "weekly_score": None,
            "daily_alarm": True,
            "weekday_alarm": False,
            "weekday_anomaly_streak_days": 2.0,
            "weekly_anomaly_streak_days": None,
            "long_term_anomaly_streak_days": 0.0,
            "weekday_exceeding_since": pd.Timestamp("2013-08-30T00:00:00+00:00"),
            "weekly_exceeding_since": None,
            "long_term_exceeding_since": None,
            "weekday_sustained": False,
            "weekly_sustained": False,
            "long_term_sustained": False,
            "sustained_drift": False,
            "anomaly_direction": "high",
            "anomaly_level": "unusual",
        }
    )


def _calendar_context() -> CalendarContext:
    return build_calendar_context(
        [],
        source_available=True,
        source="simulated_calendar",
        retrieved_at=DECISION_TIME,
        decision_time=DECISION_TIME,
        window_start=DECISION_TIME - pd.Timedelta(days=1),
        window_end=DECISION_TIME + pd.Timedelta(days=1),
        local_timezone="UTC",
    )


def _build_state(
    *,
    analysis_row: pd.Series | None = None,
    calendar_context: CalendarContext | None = None,
) -> StructuredState:
    return build_structured_state(
        decision_time=DECISION_TIME,
        analysis_row=analysis_row if analysis_row is not None else _analysis_row(),
        calendar_context=(
            calendar_context if calendar_context is not None else _calendar_context()
        ),
        local_timezone="UTC",
    )


def test_complete_structured_state_is_valid() -> None:
    state = _build_state()

    validate_structured_state(state)

    assert (
        state["observation"]["observation_start"]
        == (DECISION_TIME - pd.Timedelta(hours=1)).isoformat()
    )
    assert state["anomaly"]["available_scales"] == ["daily", "weekday", "long_term"]
    assert state["anomaly"]["sustained_scales"] == []


def test_timestamp_accepts_zulu_suffix() -> None:
    state = _build_state()
    state["decision_time"] = state["decision_time"].replace("+00:00", "Z")

    validate_structured_state(state)


def test_analysis_timestamp_must_precede_decision_time() -> None:
    analysis_row = _analysis_row()
    analysis_row["timestamp"] = DECISION_TIME

    with pytest.raises(ValueError, match="before decision_time"):
        _build_state(analysis_row=analysis_row)


def test_missing_scale_scores() -> None:
    partial_state = _build_state()
    validate_structured_state(partial_state)

    analysis_row = _analysis_row()
    for field in (
        "daily_score",
        "weekday_score",
        "weekly_score",
        "long_term_deviation_pct",
        "weekday_exceeding_since",
        "weekday_anomaly_streak_days",
        "weekly_anomaly_streak_days",
        "long_term_anomaly_streak_days",
        "anomaly_direction",
        "anomaly_level",
    ):
        analysis_row[field] = None

    missing_state = _build_state(analysis_row=analysis_row)
    validate_structured_state(missing_state)

    assert missing_state["anomaly"]["available_scales"] == []
    assert missing_state["anomaly"]["level"] is None
    assert missing_state["anomaly"]["direction"] is None


def test_invalid_calendar_context_is_rejected() -> None:
    state = _build_state()
    state["context"]["window_end"] = DECISION_TIME.isoformat()

    with pytest.raises(ValueError, match="window_end must be after"):
        validate_structured_state(state)


def test_nan_becomes_null_and_infinity_is_rejected() -> None:
    analysis_row = _analysis_row()
    analysis_row["weekday_deviation_pct"] = float("nan")

    state = _build_state(analysis_row=analysis_row)
    validate_structured_state(state)

    assert state["anomaly"]["scale_deviation_pct"]["weekday"] is None
    assert "NaN" not in json.dumps(state)

    analysis_row["weekday_deviation_pct"] = float("inf")

    with pytest.raises(ValueError, match="must be finite"):
        _build_state(analysis_row=analysis_row)


def test_value_implausible_round_trips() -> None:
    analysis_row = _analysis_row()
    analysis_row["value_implausible"] = True

    state = _build_state(analysis_row=analysis_row)
    validate_structured_state(state)

    assert state["observation"]["value_implausible"] is True


def test_value_implausible_accepts_numpy_bool() -> None:
    analysis_row = _analysis_row()
    analysis_row["value_implausible"] = np.bool_(True)

    state = _build_state(analysis_row=analysis_row)

    assert state["observation"]["value_implausible"] is True
    assert isinstance(state["observation"]["value_implausible"], bool)


def test_value_implausible_rejects_non_boolean() -> None:
    state = _build_state()
    state["observation"]["value_implausible"] = "true"  # type: ignore[typeddict-item]

    with pytest.raises(TypeError, match="must be a boolean"):
        validate_structured_state(state)


def test_value_implausible_must_not_be_missing_from_analysis_row() -> None:
    analysis_row = _analysis_row()
    del analysis_row["value_implausible"]

    with pytest.raises(ValueError, match="missing required fields"):
        _build_state(analysis_row=analysis_row)


@pytest.mark.parametrize("field", ["y_true", "scenario_id", "additional"])
def test_structured_state_rejects_additional_fields(field: str) -> None:
    state = _build_state()
    state[field] = "forbidden"  # type: ignore[literal-required]

    with pytest.raises(ValueError, match="unexpected fields"):
        validate_structured_state(state)


def test_structured_state_survives_json_roundtrip(tmp_path: Path) -> None:
    state = _build_state()
    output_file = tmp_path / "structured_state.json"

    save_json(dict(state), output_file)

    loaded_state = json.loads(output_file.read_text(encoding="utf-8"))
    validate_structured_state(loaded_state)

    assert loaded_state == state


def test_identical_inputs_produce_identical_states() -> None:
    first_state = _build_state()
    second_state = _build_state()

    assert first_state == second_state


def test_alarm_and_since_in_state() -> None:
    anomaly = _build_state()["anomaly"]

    assert anomaly["alarm_scales"] == ["daily"]
    assert anomaly["scale_exceeding_since"] == {
        "weekday": "2013-08-30",
        "weekly": None,
        "long_term": None,
    }
