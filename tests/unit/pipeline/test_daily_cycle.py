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


def _calm_series(hours: int) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    values = 200.0 + 2.0 * np.sin(2 * np.pi * index.hour.to_numpy() / 24)
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


def test_classification_is_unknown_when_reference_is_insufficient() -> None:
    # min_reference_samples default ist 100 - 45 Trainingsstunden reichen bewusst nicht, um den "zu wenig Referenzdaten" statt "normal"-Fall zu treffen
    series = _calm_series(50)
    coldstart_hours = 45
    state = _state(series.iloc[:coldstart_hours])
    decision_time = series.index[coldstart_hours] + pd.Timedelta(hours=1)
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : decision_time - pd.Timedelta(hours=1)]
    config = replace(SYS_VARIANTS["SYS1"], llm_mode="rule")

    result, _ = run_cycle(state, new_observations, decision_time, config, calendar_context=_calendar_context(decision_time))

    assert result.classification == "unknown"
    assert result.rule_output is None


def test_classification_is_normal_without_calling_the_rule_classifier() -> None:
    series = _calm_series(24 * 10)
    coldstart_hours = 24 * 8
    state = _state(series.iloc[:coldstart_hours])
    decision_time = series.index[coldstart_hours] + pd.Timedelta(hours=1)
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : decision_time - pd.Timedelta(hours=1)]
    config = replace(SYS_VARIANTS["SYS1"], llm_mode="rule")

    result, _ = run_cycle(state, new_observations, decision_time, config, calendar_context=_calendar_context(decision_time))

    assert result.analysis_row["anomaly_level"] == "normal"
    assert result.classification == "normal"
    assert result.rule_output is None


def test_sustained_absence_triggers_immediate_retrain_and_range_exclusion() -> None:
    # Werte gewählt, dass der Drop beim ersten decision_time erst 2h alt ist (unter SUSTAINED_DAILY_ELEVATED_HOURS,
    # noch "peak") und beim zweiten seit Mitternacht durchgehend 24h auffällig war (klar über der 18h-Schwelle,
    # -> "absence") -> rule_based_classifier.py
    hours = 24 * 12
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    baseline = 200.0 + 2.0 * np.sin(2 * np.pi * index.hour.to_numpy() / 24)
    drop_start = 24 * 6
    drop_len = 40
    values = baseline.copy()
    values[drop_start : drop_start + drop_len] = 5.0
    series = pd.Series(values, index=index, name="target")

    coldstart_hours = drop_start - 1
    config = SYS_VARIANTS["SYS2"]
    state = _state(series.iloc[:coldstart_hours])

    first_decision_time = series.index[drop_start + 2]
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : first_decision_time - pd.Timedelta(hours=1)]
    first_result, state = run_cycle(state, new_observations, first_decision_time, config, calendar_context=_calendar_context(first_decision_time))

    assert first_result.classification == "peak"
    assert first_result.adaption_action is not None and first_result.adaption_action.kind == "none"

    second_decision_time = series.index[drop_start + 24]
    new_observations = series.loc[state.history.index[-1] + pd.Timedelta(hours=1) : second_decision_time - pd.Timedelta(hours=1)]
    second_result, second_state = run_cycle(state, new_observations, second_decision_time, config, calendar_context=_calendar_context(second_decision_time))

    # nur  ersten 24 Drop-Stunden sind zu diesem decision_time überhaupt schon beobachtet ->  Rest von drop_len liegt in der Zukunft 
    # -> wird hier nicht ausgeschlossen
    observed_drop_end = second_decision_time - pd.Timedelta(hours=1)

    assert second_result.classification == "absence"
    assert second_result.adaption_action is not None
    assert second_result.adaption_action.kind == "exclude_range"
    assert second_result.adaption_action.range_start == index[drop_start]
    assert second_result.adaption_action.range_end == observed_drop_end
    assert second_result.retrained
    assert second_result.reference_reset

    excluded = second_state.history.loc[index[drop_start] : observed_drop_end]
    assert excluded.isna().all()
    assert not second_state.history.loc[: index[drop_start - 1]].isna().any()
