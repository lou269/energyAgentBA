from dataclasses import dataclass

import pandas as pd
from prophet import Prophet

from src.adaption.adaption_policy import AdaptionAction, adaption_policy
from src.config.config_forecasting import CycleConfig, ProphetVariantConfig
from src.context.calendar_schema import CalendarContext
from src.forecasting.prophet_model import build_prophet_forecast, fit_prophet_model, is_refit_required, select_prophet_history
from src.llm.client import LLMClient
from src.llm.gate import gate_classification
from src.llm.inference import infer_llm_output
from src.llm.llm_schema import Classification, LLMOutput
from src.llm.rule_based_classifier import RuleClassificationResult, rule_based_classify
from src.numerical_analysis.daily_analysis import compute_analysis_row
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_schema import StructuredState


@dataclass(frozen=True)
class CycleState:
    history: pd.Series
    prophet_model: Prophet | None
    model_history: pd.Series | None
    model_fitted_at: pd.Timestamp | None
    fixed_history: pd.Series | None = None


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
    new_value_implausible: pd.Series | None = None,
) -> tuple[CycleResult, CycleState]:
    if config.event_adaptation and config.llm_mode == "off":
        raise ValueError("event_adaptation requires llm_mode to be 'rule' or 'real'.")

    if not state.history.empty:
        expected_start = state.history.index[-1] + pd.Timedelta(hours=1)
        if new_observations.index[0] != expected_start:
            raise ValueError("new_observations must continue directly after state.history.")

    if new_observations.index[-1] != decision_time - pd.Timedelta(hours=1):
        raise ValueError("new_observations must end exactly one hour before decision_time.")

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
        retraining_interval_hours=variant.retraining_interval_hours,
    )

    if fit_required:
        prophet_model, model_history = _fit_variant(fixed_history, history, decision_time, config, variant, local_timezone)
        model_fitted_at = decision_time
    else:
        assert state.prophet_model is not None
        assert state.model_history is not None
        prophet_model = state.prophet_model
        model_history = state.model_history
        model_fitted_at = state.model_fitted_at

    forecast = _build_forecast(prophet_model, model_history, decision_time, config, variant, local_timezone)

    # None, solange die History (z.B. direkt nach einem Reset) kürzer als reference_window_hours ist
    analysis_row = compute_analysis_row(
        history,
        target_timestamp=decision_time - pd.Timedelta(hours=1),
        config=config.numerical_analysis_config,
        local_timezone=local_timezone,
        raw_value_implausible=new_value_implausible,
    )

    structured_state: StructuredState | None = None
    classification: Classification | None = None
    llm_output: LLMOutput | None = None
    rule_output: RuleClassificationResult | None = None
    adaption_action: AdaptionAction | None = None

    if analysis_row is not None and config.llm_mode != "off":
        if calendar_context is None:
            raise ValueError("calendar_context is required unless llm_mode is 'off'.")

        structured_state = build_structured_state(
            decision_time=decision_time,
            analysis_row=analysis_row,
            forecast_rows=forecast,
            calendar_context=calendar_context,
        )

        classification, llm_output, rule_output = _classify(structured_state, config, local_timezone, llm_client, llm_prompt)

        if config.event_adaptation:
            adaption_action = adaption_policy(
                classification,
                structured_state,
                streak_tolerance_window_days=config.numerical_analysis_config.streak_tolerance_window_days,
            )

    reference_reset = False

    if adaption_action is not None and adaption_action.kind != "none":
        history = _apply_adaption(history, adaption_action)

        prophet_model, model_history = _fit_variant(fixed_history, history, decision_time, config, variant, local_timezone)
        model_fitted_at = decision_time
        forecast = _build_forecast(prophet_model, model_history, decision_time, config, variant, local_timezone)

        fit_required = True
        reference_reset = True

    new_state = CycleState(
        history=history,
        prophet_model=prophet_model,
        model_history=model_history,
        model_fitted_at=model_fitted_at,
        fixed_history=fixed_history,
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
    )

    return result, new_state


def _classify(
    structured_state: StructuredState,
    config: CycleConfig,
    local_timezone: str,
    llm_client: LLMClient | None,
    llm_prompt: str | None,
) -> tuple[Classification, LLMOutput | None, RuleClassificationResult | None]:
    classification = gate_classification(structured_state)
    if classification is not None:
        return classification, None, None

    if config.llm_mode == "rule":
        rule_output = rule_based_classify(structured_state, local_timezone=local_timezone)
        return rule_output.classification, None, rule_output

    if llm_client is None or llm_prompt is None or config.llm_config is None:
        raise ValueError("llm_client, llm_prompt and config.llm_config are required when llm_mode is 'real'.")

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
    )

    return inference_result.output["classification"], inference_result.output, None


def _build_forecast(
    prophet_model: Prophet,
    model_history: pd.Series,
    decision_time: pd.Timestamp,
    config: CycleConfig,
    variant: ProphetVariantConfig,
    local_timezone: str,
) -> pd.DataFrame:
    target_index = pd.date_range(
        start=decision_time,
        periods=config.forecasting_config.horizon_hours,
        freq=config.forecasting_config.frequency,
    )

    raw_forecast = build_prophet_forecast(
        prophet_model,
        target_index,
        clip_negative_forecasts=config.forecasting_config.negative_forecast_handling == "clip_zero",
        history_end=model_history.index[-1],
        local_timezone=local_timezone,
        log_transform=config.forecasting_config.log_transform,
    )

    forecast = raw_forecast.reset_index()[["target_timestamp", "y_pred", "y_lower", "y_upper"]].copy()
    forecast["run_id"] = f"cycle_{decision_time.strftime('%Y%m%dT%H%M')}"
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
) -> tuple[Prophet, pd.Series]:
    forecasting_config = config.forecasting_config

    model_history = select_prophet_history(
        fixed_history,
        available_history,
        forecast_origin=decision_time,
        history_mode=variant.history_mode,
        rolling_window_hours=variant.rolling_window_hours,
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
    )

    return model, model_history


def _apply_adaption(
    history: pd.Series,
    action: AdaptionAction
) -> pd.Series:
    assert action.new_history_start is not None
    return history.loc[history.index >= action.new_history_start]


