# python -m pytest tests/unit/experiments/k3_adaptation/test_k3_oracle.py -v

import numpy as np
import pandas as pd

from experiments.k3_adaptation.k3_oracle import (
    _apply_strategy,
    event_days,
    trigger_actions,
)
from src.pipeline.daily_cycle import CycleState


def _state_with_masked_day() -> tuple[CycleState, pd.Series, pd.Timestamp]:
    index = pd.date_range("2024-01-01", periods=24 * 10, freq="1h", tz="UTC")
    target = pd.Series(np.arange(len(index), dtype=float), index=index, name="target")
    history = target.loc[: pd.Timestamp("2024-01-08 23:00", tz="UTC")].copy()
    # Tag 6 fehlt dem Zyklus, in der Originalreihe ist er da
    history.loc["2024-01-06"] = np.nan
    state = CycleState(
        history=history, prophet_model=None, model_history=None, model_fitted_at=None
    )

    return state, target, pd.Timestamp("2024-01-04", tz="UTC")


def test_cut_restarts_the_history_from_the_original_series() -> None:
    state, target, change_start = _state_with_masked_day()

    cut = _apply_strategy(state, "cut", change_start, target)

    assert cut.history.index[0] == change_start
    assert cut.history.index[-1] == state.history.index[-1]
    assert not cut.history.isna().any()


def test_step_regressor_keeps_the_history_and_sets_the_start() -> None:
    state, target, change_start = _state_with_masked_day()

    stepped = _apply_strategy(state, "step_regressor", change_start, target)

    assert stepped.level_shift_start == change_start
    assert stepped.history.equals(state.history)


def test_none_leaves_the_state_untouched() -> None:
    state, target, change_start = _state_with_masked_day()

    assert _apply_strategy(state, "none", change_start, target) is state


def test_trigger_is_set_on_the_local_trigger_day() -> None:
    # 17.07. 00:00 lokal ist in BST der 16.07. 23:00 UTC
    actions = trigger_actions("cut", "2014-07-15", 2)

    assert list(actions) == [pd.Timestamp("2014-07-16 23:00", tz="UTC")]
    assert trigger_actions("none", "2014-07-15", None) == {}


def test_event_days_are_local_calendar_days() -> None:
    days = event_days("2014-07-15", ((2, "peak"), (5, "stuck")))

    assert [day.strftime("%Y-%m-%d") for day in days] == ["2014-07-17", "2014-07-20"]
