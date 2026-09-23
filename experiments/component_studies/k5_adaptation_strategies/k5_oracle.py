from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pandas as pd

from experiments.component_studies.k5_adaptation_strategies.k5_config import K5Strategy
from src.adaption.adaption_policy import AdaptionAction, pattern_change_start
from src.common.timestamps import analyzed_day_index, local_day_index, local_midnight_utc
from src.config.config_forecasting import CycleConfig
from src.forecasting.evaluation import score_cycle_forecast
from src.pipeline.comparison_harness import ScenarioData, coldstart_history, observations_since
from src.pipeline.daily_cycle import CycleState, apply_adaption, run_cycle


def run_oracle(
    scenario: ScenarioData,
    config: CycleConfig,
    *,
    actions: Mapping[pd.Timestamp, K5Strategy],
    streak_tolerance_window_days: int,
    local_timezone: str,
    masked_days: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """Zyklus wie SYS1, Adaptionen kommen von außen (actions je decision_time) statt vom Detektor"""
    np.random.seed(config.forecasting_config.seed)

    # ausgeblendet wird nur, was der Zyklus zu sehen bekommt, der MAE rechnet weiter gegen die echten Werte
    observed = scenario.target_series
    if masked_days is not None:
        observed = observed.mask(local_day_index(observed.index, local_timezone).isin(masked_days))

    state = CycleState(
        history=coldstart_history(scenario.target_series, scenario.decision_times[0], local_timezone),
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
    )
    mae_values: list[float] = []

    for decision_time in scenario.decision_times:
        # vor dem Fit, wirkt also schon auf die Prognose dieses Tages wie der Neu-Fit nach einer Adaption in run_cycle
        if decision_time in actions:
            change_start = pattern_change_start(decision_time, streak_tolerance_window_days, local_timezone)
            state = _apply_strategy(state, actions[decision_time], change_start, scenario.target_series)

        new_observations = observations_since(observed, state.history, decision_time)
        result, state = run_cycle(state, new_observations, decision_time, config, local_timezone=local_timezone)

        mae_w, _ = score_cycle_forecast(
            result.forecast, scenario.target_series, scenario.target_imputed, config.forecasting_config.mape_min_eligible_watts
        )
        mae_values.append(mae_w)

    return pd.DataFrame({"decision_time": scenario.decision_times, "mae_w": mae_values})


# fester Triggertag, none hat keinen
def trigger_actions(
    strategy: K5Strategy,
    cutover_date: str,
    trigger_day: int | None,
    local_timezone: str,
) -> dict[pd.Timestamp, K5Strategy]:
    if trigger_day is None:
        return {}

    return {local_midnight_utc(cutover_date, local_timezone, days_offset=trigger_day): strategy}


# SYS2 nachspielen: an jedem Reset-Tag schneiden wie advance_history_start
def replay_actions(decisions: pd.DataFrame) -> dict[pd.Timestamp, K5Strategy]:
    resets = decisions.loc[decisions["adaption_action"].eq("advance_history_start"), "decision_time"]
    return {decision_time: "cut" for decision_time in resets}


def replay_masked_days(
    decisions: pd.DataFrame,
    *,
    masked_classifications: tuple[str, ...],
    local_timezone: str,
) -> pd.DatetimeIndex | None:
    if not masked_classifications:
        return None

    unusual = decisions.loc[decisions["classification"].isin(masked_classifications), "decision_time"]
    return analyzed_day_index(pd.Index(unusual), local_timezone)


def _apply_strategy(
    state: CycleState,
    strategy: K5Strategy,
    change_start: pd.Timestamp,
    target_series: pd.Series,
) -> CycleState:
    if strategy == "cut":
        # aus den Originaldaten, damit ausgeblendete Tage ab t_c wieder drin sind (new_pattern nimmt sie als neues Normal auf)
        action = AdaptionAction(kind="advance_history_start", new_history_start=change_start)
        return replace(state, history=apply_adaption(target_series.loc[: state.history.index[-1]], action))

    if strategy == "step_regressor":
        return replace(state, level_shift_start=change_start)

    return state
