from dataclasses import dataclass, field

import pandas as pd
from prophet import Prophet

from src.adaption.adaption_policy import (
    AdaptionAction,
    adaption_policy,
    add_excluded_window,
    apply_adaption,
    ended_windows,
    mask_excluded_windows,
)
from src.common.timestamps import local_day_hours, shift_local_days
from src.config.config_forecasting import CycleConfig, ProphetVariantConfig
from src.context.calendar_schema import CalendarContext
from src.forecasting.prophet_model import (
    build_prophet_forecast,
    fit_prophet_model,
    is_refit_required,
    select_prophet_history,
)
from src.llm.calendar_tool import CalendarLookup
from src.llm.client import LLMClient, ToolCallResponse
from src.llm.gate import gate_classification
from src.llm.inference import LLMInferenceError, infer_llm_output
from src.llm.llm_schema import Classification, LLMOutput
from src.llm.rule_based_classifier import RuleClassificationResult, rule_based_classify
from src.numerical_analysis.daily_analysis import (
    add_level_shift_streaks,
    compute_analysis_row,
)
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_schema import StructuredState


@dataclass(frozen=True)
class CycleState:
    history: pd.Series
    prophet_model: Prophet | None
    model_history: pd.Series | None
    model_fitted_at: pd.Timestamp | None
    fixed_history: pd.Series | None = None
    level_shift_start: pd.Timestamp | None = None
    # nach absence ausgeschlossene Kalenderfenster, fehlen bei Fit und Referenz, bleiben aber in history
    excluded_windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...] = ()
    score_history: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass(frozen=True)
class CycleResult:
    decision_time: pd.Timestamp
    forecast: pd.DataFrame
    analysis_row: pd.Series | None
    retrained: bool
    reference_reset: bool
    structured_state: StructuredState | None
    classification: Classification | None
    llm_output: LLMOutput | None
    rule_output: RuleClassificationResult | None
    adaption_action: AdaptionAction | None
    llm_error: LLMInferenceError | None = None
    calendar_tool_response: ToolCallResponse | None = None


def run_cycle(
    state: CycleState,
    new_observations: pd.Series,
    decision_time: pd.Timestamp,
    config: CycleConfig,
    *,
    local_timezone: str,
    llm_client: LLMClient | None = None,
    llm_prompt: str | None = None,
    calendar_context: CalendarContext | None = None,
    calendar_lookup: CalendarLookup | None = None,
    new_value_implausible: pd.Series | None = None,
) -> tuple[CycleResult, CycleState]:
    if config.event_adaptation and config.llm_mode == "off":
        raise ValueError("event_adaptation requires llm_mode to be 'rule' or 'real'.")

    if not state.history.empty:
        expected_start = state.history.index[-1] + pd.Timedelta(hours=1)
        if new_observations.index[0] != expected_start:
            raise ValueError(
                "new_observations must continue directly after state.history."
            )

    if new_observations.index[-1] != decision_time - pd.Timedelta(hours=1):
        raise ValueError(
            "new_observations must end exactly one hour before decision_time."
        )

    target_column = new_observations.name
    history = pd.concat([state.history, new_observations]).sort_index()
    history.name = target_column

    variant = config.forecasting_config.selected_prophet_variant

    fixed_history = state.fixed_history if state.fixed_history is not None else history

    fit_required = is_refit_required(
        state.prophet_model is not None,
        history_mode=variant.history_mode,
        fitted_at=state.model_fitted_at,
        current_time=decision_time,
        retraining_interval_days=variant.retraining_interval_days,
        local_timezone=local_timezone,
    )

    excluded_windows = state.excluded_windows
    score_history = state.score_history
    analysis_config = config.numerical_analysis_config

    # Der analysierte Tag bleibt auch im ausgeschlossenen Fenster drin, sonst wäre er ein measurement_error
    analyzed_day_start = shift_local_days(decision_time, -1, local_timezone)

    analysis_row = compute_analysis_row(
        mask_excluded_windows(history, excluded_windows, keep_from=analyzed_day_start),
        target_timestamp=decision_time - pd.Timedelta(hours=1),
        config=analysis_config,
        local_timezone=local_timezone,
        raw_value_implausible=new_value_implausible,
    )

    if analysis_row is not None:
        analysis_row, score_history = add_level_shift_streaks(
            analysis_row,
            score_history,
            config=analysis_config,
            local_timezone=local_timezone,
        )

    structured_state: StructuredState | None = None
    classification: Classification | None = None
    llm_output: LLMOutput | None = None
    rule_output: RuleClassificationResult | None = None
    adaption_action: AdaptionAction | None = None
    llm_error: LLMInferenceError | None = None
    calendar_tool_response: ToolCallResponse | None = None

    if analysis_row is not None and config.llm_mode != "off":
        if calendar_context is None:
            raise ValueError("calendar_context is required unless llm_mode is 'off'.")

        structured_state = build_structured_state(
            decision_time=decision_time,
            analysis_row=analysis_row,
            calendar_context=calendar_context,
            local_timezone=local_timezone,
        )

        # mit Kalender-Tool kommt der State mit dem geholten Kalender zurück, die Adaption braucht dessen Einträge
        # scheitert das LLM, bleibt der Tag ohne Einordnung und ohne Adaption, prognostiziert wird trotzdem,
        # sonst fehlt der Tag nur in SYS3 und die Systeme werden auf verschiedenen Tagen verglichen
        try:
            (
                classification,
                llm_output,
                rule_output,
                structured_state,
                calendar_tool_response,
            ) = _classify(
                structured_state,
                config,
                local_timezone,
                llm_client,
                llm_prompt,
                calendar_lookup,
            )
        except LLMInferenceError as error:
            llm_error = error

        if config.event_adaptation and classification is not None:
            adaption_action = adaption_policy(
                classification,
                structured_state,
                streak_tolerance_window_days=analysis_config.streak_tolerance_window_days,
                window_exclusion=config.window_exclusion,
                local_timezone=local_timezone,
            )

    reference_reset = False

    if adaption_action is not None and adaption_action.kind == "advance_history_start":
        history = apply_adaption(history, adaption_action)
        reference_reset = True
        # die gespeicherten Werte hängen an der alten Referenz, nach Reset beginnt die Streak neu
        score_history = pd.DataFrame()

    if adaption_action is not None and adaption_action.kind == "exclude_window":
        excluded_windows, adaption_action = add_excluded_window(
            excluded_windows, adaption_action
        )

    # erst nach der Einordnung prognostizieren, damit eine Adaption schon in die Prognose für heute eingeht
    if adaption_action is not None and adaption_action.kind != "none":
        fit_required = True

    if fit_required:
        training_windows = ended_windows(excluded_windows, decision_time)
        prophet_model, model_history = _fit_variant(
            mask_excluded_windows(fixed_history, training_windows),
            mask_excluded_windows(history, training_windows),
            decision_time,
            config,
            variant,
            local_timezone,
            state.level_shift_start,
        )
        model_fitted_at = decision_time
    else:
        assert state.prophet_model is not None
        assert state.model_history is not None
        prophet_model = state.prophet_model
        model_history = state.model_history
        model_fitted_at = state.model_fitted_at

    forecast = _build_forecast(
        prophet_model, model_history, decision_time, config, variant, local_timezone
    )

    new_state = CycleState(
        history=history,
        prophet_model=prophet_model,
        model_history=model_history,
        model_fitted_at=model_fitted_at,
        fixed_history=fixed_history,
        level_shift_start=state.level_shift_start,
        excluded_windows=excluded_windows,
        score_history=score_history,
    )

    result = CycleResult(
        decision_time=decision_time,
        forecast=forecast,
        analysis_row=analysis_row,
        retrained=fit_required,
        reference_reset=reference_reset,
        structured_state=structured_state,
        classification=classification,
        llm_output=llm_output,
        rule_output=rule_output,
        adaption_action=adaption_action,
        llm_error=llm_error,
        calendar_tool_response=calendar_tool_response,
    )

    return result, new_state


def _classify(
    structured_state: StructuredState,
    config: CycleConfig,
    local_timezone: str,
    llm_client: LLMClient | None,
    llm_prompt: str | None,
    calendar_lookup: CalendarLookup | None,
) -> tuple[
    Classification,
    LLMOutput | None,
    RuleClassificationResult | None,
    StructuredState,
    ToolCallResponse | None,
]:
    classification = gate_classification(structured_state)
    if classification is not None:
        return classification, None, None, structured_state, None

    if config.llm_mode == "rule":
        rule_output = rule_based_classify(
            structured_state,
            local_timezone=local_timezone,
            min_sustained_scales=config.numerical_analysis_config.min_sustained_scales,
        )
        return rule_output.classification, None, rule_output, structured_state, None

    if llm_client is None or llm_prompt is None or config.llm_config is None:
        raise ValueError(
            "llm_client, llm_prompt and config.llm_config are required when llm_mode is 'real'."
        )

    inference_result = infer_llm_output(
        structured_state,
        client=llm_client,
        prompt=llm_prompt,
        model=config.llm_config.model,
        temperature=config.llm_config.temperature,
        presence_penalty=config.llm_config.presence_penalty,
        seed=config.llm_config.seed,
        max_attempts=config.llm_config.max_attempts,
        num_predict=config.llm_config.num_predict,
        num_ctx=config.llm_config.num_ctx,
        think=config.llm_config.think,
        keep_alive=config.llm_config.keep_alive,
        calendar_lookup=calendar_lookup,
    )

    return (
        inference_result.output["classification"],
        inference_result.output,
        None,
        inference_result.state,
        inference_result.calendar_tool_response,
    )


def _build_forecast(
    prophet_model: Prophet,
    model_history: pd.Series,
    decision_time: pd.Timestamp,
    config: CycleConfig,
    variant: ProphetVariantConfig,
    local_timezone: str,
) -> pd.DataFrame:
    target_index = local_day_hours(
        decision_time,
        config.forecasting_config.horizon_days,
        config.forecasting_config.frequency,
        local_timezone,
    )

    raw_forecast = build_prophet_forecast(
        prophet_model,
        target_index,
        clip_negative_forecasts=config.forecasting_config.negative_forecast_handling
        == "clip_zero",
        history_end=model_history.index[-1],
        local_timezone=local_timezone,
        log_transform=config.forecasting_config.log_transform,
    )

    forecast = raw_forecast.reset_index()[
        ["target_timestamp", "y_pred", "y_lower", "y_upper"]
    ].copy()
    forecast["run_id"] = (
        f"cycle_{decision_time.tz_convert(local_timezone).strftime('%Y%m%dT%H%M')}"
    )
    forecast["model_id"] = variant.model_id
    forecast["config_version"] = config.forecasting_config.config_version
    forecast["forecast_origin"] = decision_time

    return forecast


def _fit_variant(
    fixed_history: pd.Series,
    available_history: pd.Series,
    decision_time: pd.Timestamp,
    config: CycleConfig,
    variant: ProphetVariantConfig,
    local_timezone: str,
    level_shift_start: pd.Timestamp | None,
) -> tuple[Prophet, pd.Series]:
    forecasting_config = config.forecasting_config

    model_history = select_prophet_history(
        fixed_history,
        available_history,
        forecast_origin=decision_time,
        history_mode=variant.history_mode,
        rolling_window_days=variant.rolling_window_days,
        local_timezone=local_timezone,
    )

    model = fit_prophet_model(
        model_history,
        growth=forecasting_config.growth,
        daily_seasonality=forecasting_config.daily_seasonality,
        weekly_seasonality=variant.weekly_seasonality,
        yearly_seasonality=variant.yearly_seasonality,
        country_holidays=forecasting_config.country_holidays,
        local_timezone=local_timezone,
        log_transform=forecasting_config.log_transform,
        interval_width=forecasting_config.interval_width,
        uncertainty_samples=forecasting_config.uncertainty_samples,
        level_shift_start=level_shift_start,
    )

    return model, model_history
