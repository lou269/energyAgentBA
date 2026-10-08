from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pandas as pd

from experiments.common.standard_config import LOCAL_TIMEZONE
from experiments.k3_adaptation.k3_config import K3Strategy
from src.adaption.adaption_policy import (
    AdaptionAction,
    apply_adaption,
    pattern_change_start,
)
from src.common.timestamps import (
    local_daily_mean,
    local_day_index,
    local_midnight_utc,
)
from src.forecasting.evaluation import score_cycle_forecast, score_daily_means
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
    actions: Mapping[pd.Timestamp, K3Strategy],
    masked_days: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    # Zyklus wie cycle_config, Adaptionen kommen von außen (actions je decision_time) statt vom Detektor.
    cycle_config = replace(cycle_config, llm_mode="off")
    np.random.seed(cycle_config.forecasting_config.seed)

    # ausgeblendet wird nur, was der Zyklus zu sehen bekommt, der MAE rechnet weiter gegen die Szenario-Reihe ohne Ausblenden
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
    forecasts: list[pd.DataFrame] = []

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
        forecasts.append(result.forecast.assign(decision_time=decision_time))

    days = score_daily_means(
        pd.concat(forecasts, ignore_index=True),
        local_daily_mean(scenario.target_series, LOCAL_TIMEZONE).tz_convert("UTC"),
        group_column="model_id",
        day_column="decision_time",
    )

    return pd.DataFrame(
        {"decision_time": scenario.decision_times, "mae_w": mae_values}
    ).merge(
        days[["decision_time", "day_bias_w", "day_error_w"]],
        on="decision_time",
        how="left",
    )


# fester Triggertag, none hat keinen
def trigger_actions(
    strategy: K3Strategy,
    cutover_date: str,
    trigger_day: int | None,
) -> dict[pd.Timestamp, K3Strategy]:
    if trigger_day is None:
        return {}

    return {
        local_midnight_utc(
            cutover_date, LOCAL_TIMEZONE, days_offset=trigger_day
        ): strategy
    }


# lokale Kalendertage der Ereignisse, die dem Zyklus fehlen sollen
def event_days(
    cutover_date: str, events: tuple[tuple[int, str], ...]
) -> pd.DatetimeIndex:
    return local_day_index(
        pd.DatetimeIndex(
            [
                local_midnight_utc(cutover_date, LOCAL_TIMEZONE, days_offset=day)
                for day, _kind in events
            ]
        ),
        LOCAL_TIMEZONE,
    )


def _apply_strategy(
    state: CycleState,
    strategy: K3Strategy,
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
