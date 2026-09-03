# python -m pytest tests/unit/test_structured_state.py -v
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from src.context.calendar_context import build_calendar_context
from src.context.calendar_schema import CalendarContext
from src.pipeline.io import save_json
from src.structured_state.builder import build_structured_state
from src.structured_state.schema import StructuredState, validate_structured_state


DECISION_TIME = pd.Timestamp("2013-09-02T00:00:00+00:00")


def _analysis_row() -> pd.Series:
    return pd.Series(
        {
            "timestamp": DECISION_TIME - pd.Timedelta(hours=1),
            "split": "validation",
            "current_power": 120.0,
            "short_term_mean": 110.0,
            "daily_expected": 100.0,
            "weekly_expected": 105.0,
            "long_term_mean": 108.0,
            "trend_slope_w_per_hour": 1.5,
            "trend_change": 0.2,
            "trend": "increasing",
            "short_term_score": 1.0,
            "daily_score": 2.0,
            "weekly_score": None,
            "long_term_score": 0.5,
            "anomaly_score": 2.0,
            "dominant_scale": "daily",
            "anomaly_direction": "high",
            "anomaly_level": "unusual",
        }
    )


def _forecast_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "run_id": "validation-run",
                "split": "validation",
                "model_id": "B3",
                "config_version": "0.5",
                "forecast_origin": DECISION_TIME,
                "target_timestamp": DECISION_TIME
                + pd.Timedelta(hours=index),
                "y_pred": 100.0 + index,
                "y_lower": 90.0 + index,
                "y_upper": 110.0 + index,
                "y_true": 200.0 + index,
                "scenario_id": "vacation",
            }
            for index in range(24)
        ]
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
    )


def _build_state(
    *,
    analysis_row: pd.Series | None = None,
    forecast_rows: pd.DataFrame | None = None,
    calendar_context: CalendarContext | None = None,
) -> StructuredState:
    return build_structured_state(
        decision_time=DECISION_TIME,
        analysis_row=analysis_row if analysis_row is not None else _analysis_row(),
        forecast_rows=forecast_rows if forecast_rows is not None else _forecast_rows(),
        calendar_context=(
            calendar_context
            if calendar_context is not None
            else _calendar_context()
        ),
    )


def test_complete_structured_state_is_valid() -> None:
    state = _build_state()

    validate_structured_state(state)

    assert state["observation"]["observation_start"] == (
        DECISION_TIME - pd.Timedelta(hours=1)
    ).isoformat()
    assert len(state["forecast"]["points"]) == 24
    assert state["anomaly"]["available_scales"] == [
        "short_term",
        "daily",
        "long_term",
    ]

    serialized = json.dumps(state)
    assert "y_true" not in serialized
    assert "scenario_id" not in serialized


def test_analysis_timestamp_must_precede_decision_time_by_one_hour() -> None:
    analysis_row = _analysis_row()
    analysis_row["timestamp"] = DECISION_TIME

    with pytest.raises(ValueError, match="exactly one hour before"):
        _build_state(analysis_row=analysis_row)


def test_analysis_and_forecast_split_must_match() -> None:
    forecast_rows = _forecast_rows()
    forecast_rows["split"] = "test"

    with pytest.raises(ValueError, match="same split"):
        _build_state(forecast_rows=forecast_rows)


def test_forecast_requires_exactly_24_consecutive_points() -> None:
    with pytest.raises(ValueError, match="exactly 24 rows"):
        _build_state(forecast_rows=_forecast_rows().iloc[:-1])

    state = _build_state()
    state["forecast"]["points"][1]["timestamp"] = (
        DECISION_TIME + pd.Timedelta(hours=2)
    ).isoformat()

    with pytest.raises(ValueError, match="consecutive hourly timestamps"):
        validate_structured_state(state)


def test_prediction_must_be_inside_available_interval() -> None:
    state = _build_state()
    state["forecast"]["points"][0]["predicted_power_w"] = 120.0

    with pytest.raises(ValueError):
        validate_structured_state(state)


def test_forecast_summary_must_match_points() -> None:
    state = _build_state()
    state["forecast"]["summary"]["mean_w"] = 0.0

    with pytest.raises(ValueError, match="mean_w must match"):
        validate_structured_state(state)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", 1.0),
        ("dominant_scale", "short_term"),
        ("direction", "low"),
    ],
)
def test_aggregate_anomaly_fields_must_match_scale_scores(
    field: str,
    value: object,
) -> None:
    state = _build_state()
    state["anomaly"][field] = value  # type: ignore[literal-required]

    with pytest.raises(ValueError):
        validate_structured_state(state)


def test_partial_and_missing_scale_scores_are_explicit() -> None:
    partial_state = _build_state()
    validate_structured_state(partial_state)

    analysis_row = _analysis_row()
    for field in (
        "short_term_score",
        "daily_score",
        "weekly_score",
        "long_term_score",
        "anomaly_score",
        "dominant_scale",
        "anomaly_direction",
        "anomaly_level",
    ):
        analysis_row[field] = None

    missing_state = _build_state(analysis_row=analysis_row)
    validate_structured_state(missing_state)

    assert missing_state["anomaly"]["available_scales"] == []
    assert missing_state["anomaly"]["score"] is None
    assert missing_state["anomaly"]["level"] is None
    assert missing_state["anomaly"]["direction"] is None
    assert missing_state["anomaly"]["dominant_scale"] is None


def test_invalid_calendar_context_is_rejected() -> None:
    state = _build_state()
    state["context"]["window_end"] = DECISION_TIME.isoformat()

    with pytest.raises(ValueError, match="window_end must be after"):
        validate_structured_state(state)


def test_nan_becomes_null_and_infinity_is_rejected() -> None:
    analysis_row = _analysis_row()
    analysis_row["current_power"] = float("nan")

    state = _build_state(analysis_row=analysis_row)
    validate_structured_state(state)

    assert state["observation"]["current_power_w"] is None
    assert "NaN" not in json.dumps(state)

    analysis_row["current_power"] = float("inf")

    with pytest.raises(ValueError, match="must be finite"):
        _build_state(analysis_row=analysis_row)


@pytest.mark.parametrize("field", ["y_true", "scenario_id", "additional"])
def test_structured_state_rejects_additional_fields(field: str) -> None:
    state = deepcopy(_build_state())
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