# python -m pytest tests/unit/proposal_experiments/e2_absence -v

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.proposal_experiments.e2_absence.e2_scenarios import build_ctx_scenarios
from src.config.project_config import ProjectConfig
from src.pipeline.cycle_variants import SYS_VARIANTS
from src.pipeline.comparison_harness import run_comparison
from src.pipeline.daily_cycle import CycleState, run_cycle
from src.context.calendar_context import build_calendar_context

PROJECT_ROOT = ProjectConfig().project_root


def _series(hours: int) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    hour_of_day = index.hour.to_numpy()
    values = 200.0 + 50.0 * np.sin(2 * np.pi * hour_of_day / 24) + 10.0
    return pd.Series(values, index=index, name="target")


def test_ctx0_has_no_calendar_source() -> None:
    series = _series(240)
    decision_times = (series.index[100],)
    events = ({"event_id": "e", "event_type": "absence", "start": "2024-01-01T00:00:00+00:00", "end": "2024-01-02T00:00:00+00:00", "known_at": "2023-12-01T00:00:00+00:00"},)

    ctx0, _ = build_ctx_scenarios(series, coldstart_hours=72, decision_times=decision_times, calendar_events=events)

    assert ctx0.calendar_source_available is False
    assert ctx0.calendar_events == ()


def test_ctx1_carries_the_same_events_as_ctx0_input() -> None:
    series = _series(240)
    decision_times = (series.index[100],)
    events = ({"event_id": "e", "event_type": "absence", "start": "2024-01-01T00:00:00+00:00", "end": "2024-01-02T00:00:00+00:00", "known_at": "2023-12-01T00:00:00+00:00"},)

    _, ctx1 = build_ctx_scenarios(series, coldstart_hours=72, decision_times=decision_times, calendar_events=events)

    assert ctx1.calendar_source_available is True
    assert ctx1.calendar_events == events


def test_ctx0_and_ctx1_share_identical_series_and_timing() -> None:
    series = _series(240)
    decision_times = (series.index[100], series.index[150])

    ctx0, ctx1 = build_ctx_scenarios(series, coldstart_hours=72, decision_times=decision_times, calendar_events=())

    assert ctx0.target_series.equals(ctx1.target_series)
    assert ctx0.coldstart_hours == ctx1.coldstart_hours
    assert ctx0.decision_times == ctx1.decision_times


def test_ctx1_structured_state_carries_the_calendar_event_through_run_cycle() -> None:
    # Nachweis: Kalender-Event kommt im Structured State, ohne würde CTX1 LLM gar keinen Kontext liefern
    series = _series(240)
    coldstart_hours = 144
    decision_time = series.index[coldstart_hours] + pd.Timedelta(hours=1)
    event = {
        "event_id": "vacation-test",
        "event_type": "absence",
        "start": (decision_time - pd.Timedelta(hours=12)).isoformat(),
        "end": (decision_time + pd.Timedelta(hours=12)).isoformat(),
        "known_at": (decision_time - pd.Timedelta(days=30)).isoformat(),
    }

    state = CycleState(
        history=series.iloc[:coldstart_hours],
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
        reference_window_end=None,
    )
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : decision_time - pd.Timedelta(hours=1)]

    calendar_context = build_calendar_context(
        [event],
        source_available=True,
        source="user_calendar",
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=decision_time - pd.Timedelta(hours=24),
        window_end=decision_time + pd.Timedelta(hours=24),
    )

    config = replace(SYS_VARIANTS["SYS1"], llm_mode="rule")

    result, _ = run_cycle(state, new_observations, decision_time, config, calendar_context=calendar_context)

    assert result.structured_state is not None
    assert result.structured_state["context"]["source_available"] is True
    assert [e["event_id"] for e in result.structured_state["context"]["events"]] == ["vacation-test"]


def test_run_comparison_completes_for_both_ctx_scenarios(tmp_path: Path) -> None:
 
    series = _series(480)
    coldstart_hours = 200
    decision_times = tuple(pd.date_range(start=series.index[coldstart_hours] + pd.Timedelta(hours=1), periods=3, freq="24h", tz="UTC"))
    event = {
        "event_id": "vacation-test",
        "event_type": "absence",
        "start": decision_times[0].isoformat(),
        "end": decision_times[-1].isoformat(),
        "known_at": (decision_times[0] - pd.Timedelta(days=30)).isoformat(),
    }

    ctx0, ctx1 = build_ctx_scenarios(series, coldstart_hours=coldstart_hours, decision_times=decision_times, calendar_events=(event,))

    config = {"SYS2": SYS_VARIANTS["SYS2"]}

    ctx0_dir, ctx1_dir = tmp_path / "ctx0", tmp_path / "ctx1"
    ctx0_dir.mkdir()
    ctx1_dir.mkdir()

    ctx0_result = run_comparison(ctx0, config, ctx0_dir, PROJECT_ROOT)
    ctx1_result = run_comparison(ctx1, config, ctx1_dir, PROJECT_ROOT)

    assert len(ctx0_result) == len(decision_times)
    assert len(ctx1_result) == len(decision_times)