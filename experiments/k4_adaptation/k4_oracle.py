from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.k4_adaptation.k4_config import K4Strategy
from src.adaption.adaption_policy import (
    AdaptionAction,
    apply_adaption,
    pattern_change_start,
)
from src.common.timestamps import (
    analyzed_day_index,
    local_day_index,
    local_midnight_utc,
)
from src.forecasting.evaluation import (
    score_cycle_forecast,
    score_daily_mean_bias,
)
from src.pipeline.comparison_harness import (
    ScenarioData,
    coldstart_history,
    observations_since,
)
from src.config.config_forecasting import CycleConfig
from src.pipeline.daily_cycle import CycleState, run_cycle


def run_oracle(
    scenario: ScenarioData,
    cycle_config: CycleConfig,
    actions: Mapping[pd.Timestamp, K4Strategy],
    masked_days: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    # Zyklus wie cycle_config, Adaptionen kommen von außen (actions je decision_time) statt vom Detektor.
    cycle_config = replace(cycle_config, llm_mode="off")
    np.random.seed(cycle_config.forecasting_config.seed)

    # ausgeblendet wird nur, was der Zyklus zu sehen bekommt, der MAE rechnet weiter gegen die echten Werte
    observed = scenario.target_series
    if masked_days is not None:
        observed = observed.mask(
            local_day_index(observed.index, LOCAL_TIMEZONE).isin(masked_days)
        )

    state = CycleState(
        history=coldstart_history(
            scenario.target_series, scenario.decision_times[0], LOCAL_TIMEZONE
        ),
        prophet_model=None,
        model_history=None,
        model_fitted_at=None,
    )
    mae_values: list[float] = []
    daily_bias_values: list[float] = []

    for decision_time in scenario.decision_times:
        # vor dem Fit, wirkt also schon auf die Prognose dieses Tages wie der Neu-Fit nach einer Adaption in run_cycle
        if decision_time in actions:
            change_start = pattern_change_start(
                decision_time,
                cycle_config.numerical_analysis_config.streak_tolerance_window_days,
                LOCAL_TIMEZONE,
            )
            state = _apply_strategy(
                state, actions[decision_time], change_start, scenario.target_series
            )

        new_observations = observations_since(observed, state.history, decision_time)
        result, state = run_cycle(
            state,
            new_observations,
            decision_time,
            cycle_config,
            local_timezone=LOCAL_TIMEZONE,
        )

        mae_w, _ = score_cycle_forecast(
            result.forecast,
            scenario.target_series,
            scenario.target_imputed,
            cycle_config.forecasting_config.mape_min_eligible_watts,
        )
        mae_values.append(mae_w)
        daily_bias_values.append(
            score_daily_mean_bias(
                result.forecast,
                scenario.target_series,
                scenario.target_imputed,
            )
        )

    return pd.DataFrame(
        {
            "decision_time": scenario.decision_times,
            "mae_w": mae_values,
            "day_bias_w": daily_bias_values,
            "day_error_w": np.abs(daily_bias_values),
        }
    )


# fester Triggertag, none hat keinen
def trigger_actions(
    strategy: K4Strategy,
    cutover_date: str,
    trigger_day: int | None,
) -> dict[pd.Timestamp, K4Strategy]:
    if trigger_day is None:
        return {}

    return {
        local_midnight_utc(
            cutover_date, LOCAL_TIMEZONE, days_offset=trigger_day
        ): strategy
    }


# SYS2 nachspielen: an jedem Reset-Tag schneiden wie advance_history_start
def replay_actions(decisions: pd.DataFrame) -> dict[pd.Timestamp, K4Strategy]:
    resets = decisions.loc[
        decisions["adaption_action"].eq("advance_history_start"), "decision_time"
    ]
    return {decision_time: "cut" for decision_time in resets}


def replay_masked_days(
    decisions: pd.DataFrame, masked_classifications: tuple[str, ...]
) -> pd.DatetimeIndex | None:
    if not masked_classifications:
        return None

    unusual = decisions.loc[
        decisions["classification"].isin(masked_classifications), "decision_time"
    ]
    return analyzed_day_index(pd.Index(unusual), LOCAL_TIMEZONE)


def _apply_strategy(
    state: CycleState,
    strategy: K4Strategy,
    change_start: pd.Timestamp,
    target_series: pd.Series,
) -> CycleState:
    if strategy == "cut":
        # aus den Originaldaten, damit ausgeblendete Tage ab t_c wieder drin sind (new_pattern nimmt sie als neues Normal auf)
        action = AdaptionAction(
            kind="advance_history_start", new_history_start=change_start
        )
        return replace(
            state,
            history=apply_adaption(
                target_series.loc[: state.history.index[-1]], action
            ),
        )

    if strategy == "step_regressor":
        return replace(state, level_shift_start=change_start)

    return state
