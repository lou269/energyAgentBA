from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from src.context.calendar_context import build_calendar_context
from src.pipeline.cycle_variants import SYS_VARIANTS
from src.pipeline.daily_cycle import CycleState, run_cycle


def _hourly(start, values: list[float]) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index, name="target")


def _state(history: pd.Series) -> CycleState:
    return CycleState(
        history=history,
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
        reference_window_end=None,
    )


def _calendar_context(decision_time: pd.Timestamp):
    return build_calendar_context(
        [],
        source_available=False,
        source="none",
        retrieved_at=decision_time,
        decision_time=decision_time,
        window_start=decision_time - pd.Timedelta(hours=24),
        window_end=decision_time + pd.Timedelta(hours=24),
    )


def _calm_series(hours: int, *, day_jitter_w: float = 5.0, seed: int = 42) -> pd.Series:

    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    day_of_series = np.arange(hours) // 24
    jitter_by_day = np.random.default_rng(seed).normal(0.0, day_jitter_w, size=day_of_series.max() + 1)
    values = 200.0 + 2.0 * np.sin(2 * np.pi * index.hour.to_numpy() / 24) + jitter_by_day[day_of_series]
    return pd.Series(values, index=index, name="target")


def test_event_adaptation_requires_a_classification_mode() -> None:
    config = replace(SYS_VARIANTS["SYS0"], event_adaptation=True)

    with pytest.raises(ValueError, match="event_adaptation"):
        run_cycle(_state(_hourly("2024-01-01", [100.0])), _hourly("2024-01-01", [100.0]), pd.Timestamp("2024-01-01", tz="UTC"), config)


def test_decision_time_must_be_utc() -> None:
    new_observations = _hourly("2024-01-02", [100.0])

    with pytest.raises(ValueError, match="UTC"):
        run_cycle(_state(_hourly("2024-01-01", [100.0])), new_observations, pd.Timestamp("2024-01-02T01:00:00"), SYS_VARIANTS["SYS0"])


def test_new_observations_must_continue_directly_after_history() -> None:
    history = _hourly("2024-01-01", [100.0, 100.0])
    gap_observations = _hourly(history.index[-1] + pd.Timedelta(hours=2), [100.0])
    decision_time = gap_observations.index[-1] + pd.Timedelta(hours=1)

    with pytest.raises(ValueError, match="continue directly"):
        run_cycle(_state(history), gap_observations, decision_time, SYS_VARIANTS["SYS0"])


def test_new_observations_must_end_one_hour_before_decision_time() -> None:
    history = _hourly("2024-01-01", [100.0, 100.0])
    new_observations = _hourly(history.index[-1] + pd.Timedelta(hours=1), [100.0])
    wrong_decision_time = new_observations.index[-1] + pd.Timedelta(hours=2)

    with pytest.raises(ValueError, match="one hour before"):
        run_cycle(_state(history), new_observations, wrong_decision_time, SYS_VARIANTS["SYS0"])


def _run_single_cycle(series: pd.Series, coldstart_hours: int, config) -> tuple:
    
    state = _state(series.iloc[:coldstart_hours])
    decision_time = series.index[coldstart_hours + 24]
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : decision_time - pd.Timedelta(hours=1)]
    return run_cycle(state, new_observations, decision_time, config, calendar_context=_calendar_context(decision_time))


def test_classification_is_unknown_when_reference_is_insufficient() -> None:
    # min_reference_samples_daily default ist 21 - ein einziger Trainingstag reicht bewusst nicht
    series = _calm_series(24 * 6)
    config = replace(SYS_VARIANTS["SYS1"], llm_mode="rule")

    result, _ = _run_single_cycle(series, coldstart_hours=100, config=config)

    assert result.classification == "unknown"
    assert result.rule_output is None


def test_classification_is_normal_without_calling_the_rule_classifier() -> None:
    series = _calm_series(24 * 50)
    config = replace(SYS_VARIANTS["SYS1"], llm_mode="rule")

    result, _ = _run_single_cycle(series, coldstart_hours=24 * 48, config=config)

    assert result.analysis_row["anomaly_level"] == "normal"
    assert result.classification == "normal"
    assert result.rule_output is None


def test_isolated_single_hour_spike_is_diluted_by_the_daily_mean() -> None:
    series = _calm_series(24 * 50)
    coldstart_hours = 24 * 48
    values = series.to_numpy().copy()
    values[coldstart_hours] = 300.0
    series = pd.Series(values, index=series.index, name="target")
    config = replace(SYS_VARIANTS["SYS1"], llm_mode="rule")

    result, _ = _run_single_cycle(series, coldstart_hours=coldstart_hours, config=config)

   
    assert result.analysis_row["anomaly_level"] == "normal"
    assert result.classification == "normal"


def _advance_one_day(series: pd.Series, state: CycleState, config) -> tuple:
    decision_time = state.history.index[-1] + pd.Timedelta(hours=1) + pd.Timedelta(hours=24)
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : decision_time - pd.Timedelta(hours=1)]
    return run_cycle(state, new_observations, decision_time, config, calendar_context=_calendar_context(decision_time))


def test_sustained_absence_triggers_retrain_and_range_exclusion() -> None:
    hours = 24 * 90
    series = _calm_series(hours, day_jitter_w=5.0)
    values = series.to_numpy().copy()
    drop_start = 60 * 24
    values[drop_start : drop_start + 6 * 24] = 5.0
    series = pd.Series(values, index=series.index, name="target")

    config = SYS_VARIANTS["SYS2"]
    state = _state(series.iloc[:drop_start])

    # ein Tag in den Drop hinein, Streak ist noch keine 3 Tage alt -> peak, keine Adaption
    first_result, state = _advance_one_day(series, state, config)
    assert first_result.classification == "peak"
    assert first_result.adaption_action is not None and first_result.adaption_action.kind == "none"

    # zwei weitere Tage im Drop -> Streak erreicht sustained_anomaly_streak_days -> absence
    _, state = _advance_one_day(series, state, config)
    second_result, second_state = _advance_one_day(series, state, config)

    assert second_result.classification == "absence"
    assert second_result.adaption_action is not None
    assert second_result.adaption_action.kind == "exclude_range"
    assert second_result.retrained
    assert second_result.reference_reset

    excluded = second_state.history.loc[second_result.adaption_action.range_start : second_result.adaption_action.range_end]
    assert excluded.isna().all()
