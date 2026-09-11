from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

import pandas as pd
from prophet import Prophet

from src.adaption.adaption_policy import AdaptionAction, adaption_policy
from src.config.config_forecasting import ForecastingConfig,LLMConfig, NumericalAnalysisConfig, ProphetVariantConfig
from src.context.calendar_schema import CalendarContext
from src.forecasting.prophet_model import build_prophet_forecast, fit_prophet_model
from src.forecasting.walk_forward import select_prophet_history
from src.llm.client import LLMClient
from src.llm.inference import infer_llm_output
from src.llm.llm_schema import Classification, LLMOutput
from src.llm.rule_based_classifier import RuleClassificationResult, rule_based_classify
from src.numerical_analysis.anomaly_detection import build_anomaly_detection
from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_schema import StructuredState, validate_structured_state


LLMMode = Literal["off", "rule", "real"]


@dataclass(frozen=True)
class CycleConfig:
    forecasting_config: ForecastingConfig
    numerical_analysis_config: NumericalAnalysisConfig
    event_adaptation: bool
    llm_mode: LLMMode
    llm_config: LLMConfig | None = None


@dataclass(frozen=True)
class CycleState:
    history: pd.Series
    prophet_model: Prophet | None
    model_history: pd.Series | None
    model_fitted_at: pd.Timestamp | None
    reference_window_end: pd.Timestamp | None


@dataclass(frozen=True)
class CycleResult:
    decision_time: pd.Timestamp
    forecast: pd.DataFrame
    analysis_row: pd.Series
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
    llm_client: LLMClient | None = None,
    llm_prompt: str | None = None,
    calendar_context: CalendarContext | None = None,
) -> tuple[CycleResult, CycleState]:
    if config.event_adaptation and config.llm_mode == "off":
        raise ValueError("event_adaptation requires llm_mode to be 'rule' or 'real'.")

    if decision_time.tzinfo is None or str(decision_time.tz) != "UTC":
        raise ValueError("decision_time must be a timezone-aware UTC timestamp.")

    if new_observations.empty or not new_observations.name:
        raise ValueError("new_observations must be a non-empty, named pandas Series.")

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

    fit_required = state.prophet_model is None or state.model_fitted_at is None

    if not fit_required and variant.history_mode != "fixed_train":
        assert state.model_fitted_at is not None

        if variant.retraining_interval_hours is None:
            raise RuntimeError(f"{variant.model_id} has no retraining interval.")

        elapsed_hours = (decision_time - state.model_fitted_at) / pd.Timedelta(hours=1)
        fit_required = elapsed_hours >= variant.retraining_interval_hours

    if fit_required:
        # fixed_train würde hier an der aktuellen history einfrieren statt an der ursprünglichen Coldstart-Historie 
        # -> betrifft nur C1, expanding/rolling sind davon nicht berührt
        model_history = select_prophet_history(
            history,
            history,
            forecast_origin=decision_time,
            history_mode=variant.history_mode,
            rolling_window_hours=variant.rolling_window_hours,
        )

        prophet_model = _fit_variant(model_history, variant, config.forecasting_config)
        model_fitted_at = decision_time
    else:
        assert state.prophet_model is not None
        assert state.model_history is not None
        prophet_model = state.prophet_model
        model_history = state.model_history
        model_fitted_at = state.model_fitted_at

    target_index = pd.date_range(
        start=decision_time,
        periods=config.forecasting_config.horizon_hours,
        freq="1h",
    )

    raw_forecast = build_prophet_forecast(
        prophet_model,
        target_index,
        clip_negative_forecasts=config.forecasting_config.negative_forecast_handling == "clip_zero",
        history_end=model_history.index[-1],
        local_timezone=config.forecasting_config.timezone,
        log_transform=config.forecasting_config.log_transform,
    )

    forecast = raw_forecast.reset_index()[["target_timestamp", "y_pred", "y_lower", "y_upper"]].copy()
    forecast["run_id"] = f"cycle_{decision_time.strftime('%Y%m%dT%H%M')}"
    # "split" hier nur ein Platzhalter für den Abgleich mit analysis_row weiter unten, keine echte Train/Val/Test-Bedeutung wie in walk_forward.py
    forecast["split"] = "test"
    forecast["model_id"] = variant.model_id
    forecast["config_version"] = config.forecasting_config.config_version
    forecast["forecast_origin"] = decision_time

    reference_window_end = state.reference_window_end
    reference_reset = reference_window_end is None

    if reference_reset:
        if len(history) < 3:
            raise ValueError("history must contain at least 3 observed hours before numerical_analysis can be computed.")
        reference_window_end = history.index[-3]

    assert reference_window_end is not None

    analysis_row = _compute_analysis_row(
        history,
        reference_window_end=reference_window_end,
        target_timestamp=decision_time - pd.Timedelta(hours=1),
        config=config.numerical_analysis_config,
    )

    structured_state: StructuredState | None = None
    classification: Classification | None = None
    llm_output: LLMOutput | None = None
    rule_output: RuleClassificationResult | None = None
    adaption_action: AdaptionAction | None = None

    if config.llm_mode != "off":
        if calendar_context is None:
            raise ValueError("calendar_context is required unless llm_mode is 'off'.")

        structured_state = build_structured_state(
            decision_time=decision_time,
            analysis_row=analysis_row,
            forecast_rows=forecast,
            calendar_context=calendar_context,
        )
        validate_structured_state(structured_state)

        # Proposal S.8: "Bei Z-Score > Schwelle -> LLM-Klassifikation" - ohne auffälligen Score gibt es nichts zu klassifizieren, 
        # spart den LLM-/Regel-Aufruf
        anomaly_level = analysis_row["anomaly_level"]

        if anomaly_level == "normal":
            classification = "normal"
        elif pd.isna(anomaly_level):
            # zu wenig Referenzdaten für einen Score -> "weiß es nciht", nicht "alles normal"
            classification = "unknown"
        elif config.llm_mode == "real":
            if llm_client is None or llm_prompt is None or config.llm_config is None:
                raise ValueError("llm_client, llm_prompt and config.llm_config are required when llm_mode is 'real'.")

            inference_result = infer_llm_output(
                structured_state,
                client=llm_client,
                prompt=llm_prompt,
                model=config.llm_config.model,
                temperature=config.llm_config.temperature,
                seed=config.llm_config.seed,
                max_attempts=config.llm_config.max_attempts,
            )
            llm_output = inference_result.output
            classification = llm_output["classification"]

        elif config.llm_mode == "rule":
            rule_output = rule_based_classify(structured_state)
            classification = rule_output.classification

        if config.event_adaptation:
            assert classification is not None
            adaption_action = adaption_policy(classification, structured_state)

    if adaption_action is not None and adaption_action.kind != "none":
        history = _apply_adaption(history, adaption_action)

        # Prophet und die numerical_analysis-Referenz sollen die Adaption sofort sehen, nicht erst beim nächsten regulären Retraining-Intervall
        model_history = select_prophet_history(
            history,
            history,
            forecast_origin=decision_time,
            history_mode=variant.history_mode,
            rolling_window_hours=variant.rolling_window_hours,
        )
        prophet_model = _fit_variant(model_history, variant, config.forecasting_config)
        model_fitted_at = decision_time

        if len(history) < 3:
            raise ValueError("history must contain at least 3 observed hours after adaption to recompute the numerical_analysis reference.")
        reference_window_end = history.index[-3]

        fit_required = True
        reference_reset = True

    new_state = CycleState(
        history=history,
        prophet_model=prophet_model,
        model_history=model_history,
        model_fitted_at=model_fitted_at,
        reference_window_end=reference_window_end,
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


def _fit_variant(
    model_history: pd.Series,
    variant: ProphetVariantConfig,
    forecasting_config: ForecastingConfig,
) -> Prophet:
    return fit_prophet_model(
        model_history,
        growth=forecasting_config.growth,
        daily_seasonality=forecasting_config.daily_seasonality,
        weekly_seasonality=variant.weekly_seasonality,
        yearly_seasonality=forecasting_config.yearly_seasonality,
        country_holidays=forecasting_config.country_holidays,
        local_timezone=forecasting_config.timezone,
        log_transform=forecasting_config.log_transform,
        interval_width=forecasting_config.interval_width,
        uncertainty_samples=forecasting_config.uncertainty_samples,
    )


def _apply_adaption(
    history: pd.Series, 
    action: AdaptionAction
) -> pd.Series:
    if action.kind == "advance_history_start":
        assert action.new_history_start is not None
        return history.loc[history.index >= action.new_history_start]

    if action.kind == "exclude_range":
        assert action.range_start is not None and action.range_end is not None
        adapted = history.copy()
        adapted.loc[action.range_start:action.range_end] = float("nan")
        return adapted

    raise ValueError(f"unknown AdaptionAction: {action.kind}")


def _compute_analysis_row(
    history: pd.Series,
    *,
    reference_window_end: pd.Timestamp,
    target_timestamp: pd.Timestamp,
    config: NumericalAnalysisConfig,
) -> pd.Series:
    target_column = str(history.name)
    train_data, validation_data, test_data = _split_for_numerical_analysis(
        history, reference_window_end=reference_window_end, target_column=target_column
    )

    analysis = build_multi_scale_analysis(
        train_data=train_data,
        validation_data=validation_data,
        test_data=test_data,
        target_column=target_column,
        short_term_window=config.short_term_window_hourly,
        sample_period_hours=config.sample_period_hours_hourly,
        long_term_window=config.long_term_window_hourly,
        min_daily_reference_samples=config.min_daily_reference_samples,
        min_weekly_reference_samples=config.min_weekly_reference_samples,
        trend_threshold=config.trend_threshold,
        min_reference_power_w=config.min_reference_power_w,
    )

    anomaly = build_anomaly_detection(
        analysis_results=analysis,
        min_reference_samples=config.min_reference_samples,
        min_residual_std_w=config.min_residual_std_w,
        unusual_threshold=config.unusual_threshold,
        strong_anomaly_threshold=config.strong_anomaly_threshold,
        sample_period_hours=config.sample_period_hours_hourly,
    )

    row = cast(pd.Series, anomaly.loc[target_timestamp]).copy()
    row["timestamp"] = target_timestamp
    # history kommt schon aus preprocessing, Gap-Treatment/Plausibilitätscheck liegen davor -> kein zweiter Check hier
    row["value_implausible"] = False

    return row


def _split_for_numerical_analysis(
    history: pd.Series,
    *,
    reference_window_end: pd.Timestamp,
    target_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = history.to_frame(name=target_column)

    train_data = frame.loc[:reference_window_end]
    remaining = frame.loc[frame.index > reference_window_end]

    if len(remaining) < 2:
        raise ValueError("Not enough observed hours after the reference window to score validation and test.")

    validation_data = remaining.iloc[:-1]
    test_data = remaining.iloc[-1:]

    return train_data, validation_data, test_data





