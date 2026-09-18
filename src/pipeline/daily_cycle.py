from dataclasses import dataclass
from typing import cast

import pandas as pd
from prophet import Prophet

from src.adaption.adaption_policy import AdaptionAction, adaption_policy
from src.common.timestamps import local_day_index
from src.config.config_forecasting import CycleConfig, NumericalAnalysisConfig, ProphetVariantConfig
from src.context.calendar_schema import CalendarContext
from src.forecasting.prophet_model import build_prophet_forecast, refit_and_forecast
from src.llm.client import LLMClient
from src.llm.inference import infer_llm_output
from src.llm.llm_schema import Classification, LLMOutput
from src.llm.rule_based_classifier import RuleClassificationResult, rule_based_classify
from src.numerical_analysis.anomaly_detection import build_anomaly_detection
from src.numerical_analysis.multi_scale_analysis import build_daily_cycle_analysis
from src.structured_state.builder import build_structured_state
from src.structured_state.structured_state_schema import StructuredState, validate_structured_state


DAILY_ANOMALY_SCALES = {
    "daily": ("daily_std", "daily_std_expected"),
    "weekday": ("today_mean", "weekday_expected"),
    "weekly": ("weekly_mean", "weekly_mean_expected"),
    "long_term": ("long_term_window_mean", "long_term_expected"),
}

DAILY_DIRECTION_OVERRIDE_COLUMNS = {
    "daily": ("today_mean", "today_mean_expected"),
}


@dataclass(frozen=True)
class CycleState:
    history: pd.Series
    prophet_model: Prophet | None
    model_history: pd.Series | None
    model_fitted_at: pd.Timestamp | None


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
        prophet_model, model_history, forecast = _refit_and_forecast(history, decision_time, config, variant, local_timezone)
        model_fitted_at = decision_time
    else:
        assert state.prophet_model is not None
        assert state.model_history is not None
        prophet_model = state.prophet_model
        model_history = state.model_history
        model_fitted_at = state.model_fitted_at
        forecast = _build_forecast(prophet_model, model_history, decision_time, config, variant, local_timezone)

    reference_window_end = _compute_reference_window_end(
        history,
        local_timezone=local_timezone,
        max_growth_days=config.numerical_analysis_config.max_reference_window_growth_days,
    )
    reference_reset = False

    analysis_row: pd.Series | None = None
    if reference_window_end is not None:
        analysis_row = _compute_analysis_row(
            history,
            reference_window_end=reference_window_end,
            target_timestamp=decision_time - pd.Timedelta(hours=1),
            config=config.numerical_analysis_config,
            local_timezone=local_timezone,
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
        validate_structured_state(structured_state)

        # Proposal S.8: "Bei Z-Score > Schwelle -> LLM-Klassifikation" - ohne auffälligen Score gibt es nichts zu klassifizieren,
        # spart den LLM-/Regel-Aufruf
        anomaly_level = analysis_row["anomaly_level"]

        if structured_state["observation"]["value_implausible"]:
            # today_mean fehlt komplett (Tag von exclude_incomplete_days rausgekickt, siehe day_quality.py)
            # -> anomaly_score ist dadurch selbst auch NaN, würde sonst im "unknown"-Zweig landen statt hier
            classification = "measurement_error"
        elif pd.isna(anomaly_level):
            # zu wenig Referenzdaten für einen Score -> "weiß es nciht", nicht "alles normal"
            classification = "unknown"
        elif anomaly_level == "normal":
            classification = "normal"
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
                num_predict=config.llm_config.num_predict,
                num_ctx=config.llm_config.num_ctx,
                think=config.llm_config.think,
                keep_alive=config.llm_config.keep_alive,
            )
            llm_output = inference_result.output
            classification = llm_output["classification"]

        elif config.llm_mode == "rule":
            rule_output = rule_based_classify(
                structured_state,
                sustained_anomaly_streak_days=config.numerical_analysis_config.sustained_anomaly_streak_days,
                multi_scale_minimum_ratio=config.numerical_analysis_config.multi_scale_minimum_ratio,
                local_timezone=local_timezone,
            )
            classification = rule_output.classification

        if config.event_adaptation:
            assert classification is not None
            adaption_action = adaption_policy(
                classification,
                structured_state,
                streak_tolerance_window_days=config.numerical_analysis_config.streak_tolerance_window_days,
            )

    if adaption_action is not None and adaption_action.kind != "none":
        history = _apply_adaption(history, adaption_action)

        prophet_model, model_history, forecast = _refit_and_forecast(history, decision_time, config, variant, local_timezone)
        model_fitted_at = decision_time

        fit_required = True

        # Ein Musterwechsel verschiebt den Beginn der Referenzhistorie.
        if adaption_action.kind == "advance_history_start":
            reference_reset = True

    new_state = CycleState(
        history=history,
        prophet_model=prophet_model,
        model_history=model_history,
        model_fitted_at=model_fitted_at,
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
    # "split" hier nur ein Platzhalter für den Abgleich mit analysis_row weiter unten, keine echte Train/Val/Test-Bedeutung wie in walk_forward.py
    forecast["split"] = "test"
    forecast["model_id"] = variant.model_id
    forecast["config_version"] = config.forecasting_config.config_version
    forecast["forecast_origin"] = decision_time

    return forecast


def _refit_and_forecast(
    history: pd.Series,
    decision_time: pd.Timestamp,
    config: CycleConfig,
    variant: ProphetVariantConfig,
    local_timezone: str,
) -> tuple[Prophet, pd.Series, pd.DataFrame]:
    forecasting_config = config.forecasting_config
    return refit_and_forecast(
        history,
        decision_time=decision_time,
        history_mode=variant.history_mode,
        rolling_window_hours=variant.rolling_window_hours,
        growth=forecasting_config.growth,
        daily_seasonality=forecasting_config.daily_seasonality,
        weekly_seasonality=variant.weekly_seasonality,
        yearly_seasonality=variant.yearly_seasonality,
        country_holidays=forecasting_config.country_holidays,
        local_timezone=local_timezone,
        log_transform=forecasting_config.log_transform,
        interval_width=forecasting_config.interval_width,
        uncertainty_samples=forecasting_config.uncertainty_samples,
        horizon_hours=forecasting_config.horizon_hours,
        frequency=forecasting_config.frequency,
        clip_negative_forecasts=forecasting_config.negative_forecast_handling == "clip_zero",
        model_id=variant.model_id,
        config_version=forecasting_config.config_version,
    )


def _apply_adaption(
    history: pd.Series, 
    action: AdaptionAction
) -> pd.Series:
    if action.kind == "advance_history_start":
        assert action.new_history_start is not None
        return history.loc[history.index >= action.new_history_start]

    raise ValueError(f"unknown AdaptionAction: {action.kind}")


def _compute_reference_window_end(
    history: pd.Series,
    *,
    local_timezone: str,
    max_growth_days: int,
) -> pd.Timestamp | None:
    # lässt genug von der schon vorhandenen history übrig, dass nach der Tages-Aggregation noch
    # mindestens 1 Tag validation + der Zieltag als test bleiben (siehe _compute_analysis_row).
    # Wird jeden Zyklus neu berechnet statt einmalig eingefroren, damit train nach einem Reset
    # wieder mitwachsen kann, aber nur bis max_growth_days seit dem Beginn der aktuellen history,
    # danach bleibt es stehen (Drift-Schutz für die Anomalie-Baseline bei sehr langem, unverändertem Zustand)
    if len(history) < 72:
        # kurz nach einem advance_history_start-Reset mit kleinem sustained_anomaly_streak_days
        # (z.B. E1 mit 3 statt 7 Tagen) kann history vorübergehend unter die Mindestgröße fallen.
        # Analyse für diesen einen Zyklus einfach auslassen statt run_cycle abzubrechen, history
        # wächst mit den nächsten Beobachtungen automatisch wieder darüber.
        return None

    window_start = local_day_index(history.index, local_timezone).min()
    # DateOffset statt Timedelta, damit ein DST-Wechsel innerhalb von max_growth_days die Grenze
    # nicht um eine Stunde verschiebt (siehe snap_to_local_midnight_range in common/timestamps.py)
    growth_ceiling = window_start + pd.DateOffset(days=max_growth_days)
    effective_now = min(history.index[-1], growth_ceiling)

    return effective_now - pd.Timedelta(hours=71)


def _compute_analysis_row(
    history: pd.Series,
    *,
    reference_window_end: pd.Timestamp,
    target_timestamp: pd.Timestamp,
    config: NumericalAnalysisConfig,
    local_timezone: str,
) -> pd.Series:
    target_day = target_timestamp.tz_convert(local_timezone).normalize()

    analysis = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=config.trend_window_days,
        sample_period_hours=config.sample_period_hours_daily,
        long_term_window=config.long_term_window_days,
        weekly_window_days=config.weekly_window_days,
        min_weekday_reference_samples=config.min_weekday_reference_samples,
        trend_threshold=config.trend_threshold,
        min_reference_power_w=config.min_reference_power_w,
        rolling_window_min_coverage=config.rolling_window_min_coverage,
        local_timezone=local_timezone,
    )

    anomaly = build_anomaly_detection(
        analysis_results=analysis,
        min_reference_samples={
            "daily": config.min_daily_reference_samples,
            "weekday": config.min_weekday_reference_samples,
            "weekly": config.min_weekly_reference_samples,
            "long_term": config.min_longterm_reference_samples,
        },
        min_residual_std_w=config.min_residual_std_w,
        unusual_threshold=config.unusual_threshold,
        strong_anomaly_threshold=config.strong_anomaly_threshold,
        sample_period_hours=config.sample_period_hours_daily,
        streak_tolerance_window_days=config.streak_tolerance_window_days,
        rolling_window_min_coverage=config.rolling_window_min_coverage,
        local_timezone=local_timezone,
        reference_columns=DAILY_ANOMALY_SCALES,
        direction_override_columns=DAILY_DIRECTION_OVERRIDE_COLUMNS,
    )

    row = cast(pd.Series, anomaly.loc[target_day]).copy()
    row["timestamp"] = target_day
    # exclude_incomplete_days() setzt einen kompletten Tag auf NaN, wenn Lücken/Missing-Share über den Schwellen
    # liegen (siehe day_quality.py) -> today_mean ist dann NaN, das ist der einzige Fall für value_implausible hier
    row["value_implausible"] = pd.isna(row["today_mean"])
    row["anomaly_peak_timestamp"] = target_day if pd.notna(row["anomaly_score"]) else pd.NaT

    return row


