from typing import Literal, TypedDict

import numpy as np
import pandas as pd
from prophet import Prophet

from src.forecasting.baselines import build_daily_naive_forecast, build_last_value_forecast,build_weekly_naive_forecast
from src.forecasting.prophet_model import build_prophet_forecast, fit_prophet_model
from src.forecasting.forecast_schema import FORECAST_OUTPUT_COLUMNS, validate_forecast_output


class ProphetVariantParameters(TypedDict):
    model_id: str
    history_mode: Literal["fixed_train", "expanding", "rolling"]
    rolling_window_hours: int | None
    retraining_interval_hours: int | None
    weekly_seasonality: bool


_BASELINE_BUILDERS = {
    "B1": build_last_value_forecast,
    "B2": build_daily_naive_forecast,
    "B3": build_weekly_naive_forecast,
}


def build_walk_forward_forecasts(
    fixed_history: pd.Series,
    evaluation_targets: pd.Series,
    evaluation_imputation_mask: pd.Series,
    *,
    run_id: str,
    experiment_id: str,
    split: str,
    horizon_hours: int,
    forecast_origin_step_hours: int,
    frequency: str,
    baseline_model_ids: tuple[str, ...],
    prophet_variants: tuple[ProphetVariantParameters, ...],
    growth: str,
    daily_seasonality: bool,
    yearly_seasonality: bool,
    country_holidays: str | None,
    local_timezone: str,
    log_transform: bool,
    interval_width: float,
    clip_negative_forecasts: bool,
    uncertainty_samples: int,
    config_version: str,
    initial_history_start: pd.Timestamp | None = None,
    initial_history_hours: int | None = None,
    scenario_id: str | None = None,
) -> pd.DataFrame:
    if initial_history_start is not None:
        if str(initial_history_start.tz) != "UTC":
            raise ValueError("initial_history_start must use UTC.")
        fixed_history = fixed_history.loc[fixed_history.index >= initial_history_start]

    if initial_history_hours is not None:
        if initial_history_hours < 1:
            raise ValueError("initial_history_hours must be at least 1.")
        fixed_history = fixed_history.iloc[:initial_history_hours]
        if len(fixed_history) != initial_history_hours:
            raise ValueError(f"Initial history must contain exactly {initial_history_hours} hours, got {len(fixed_history)}.")

    _validate_walk_forward_data(fixed_history, evaluation_targets, evaluation_imputation_mask, frequency)

    for name, value in {"run_id": run_id, "experiment_id": experiment_id, "split": split}.items():
        if not value:
            raise ValueError(f"{name} must not be empty.")

    # Horizont-Scheduling: Ursprünge dürfen sich nicht überlappende Horizonte teilen.
    if horizon_hours < 1:
        raise ValueError("horizon_hours must be at least 1.")
    if forecast_origin_step_hours < horizon_hours:
        raise ValueError("forecast_origin_step_hours must be at least horizon_hours to prevent overlapping horizons.")

    # Prophet-weite Annahmen dieser Implementierung.
    if growth != "linear":
        raise ValueError("The current Prophet implementation only supports linear growth.")
    if not 0.0 < interval_width < 1.0:
        raise ValueError("interval_width must be between 0 and 1.")

    unknown_baselines = set(baseline_model_ids).difference(_BASELINE_BUILDERS)

    if unknown_baselines:
        raise ValueError("Unsupported baseline model IDs: " + ", ".join(sorted(unknown_baselines)))

    model_ids = [
        *baseline_model_ids,
        *(variant["model_id"] for variant in prophet_variants),
    ]

    if not model_ids:
        raise ValueError("At least one forecast model must be configured.")
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Forecast model IDs must be unique.")

    for variant in prophet_variants:
        history_mode = variant["history_mode"]
        rolling_window_hours = variant["rolling_window_hours"]
        retraining_interval_hours = variant["retraining_interval_hours"]

        if history_mode == "fixed_train":
            if rolling_window_hours is not None or retraining_interval_hours is not None:
                raise ValueError(f"{variant['model_id']}: fixed_train must not define a rolling window or retraining interval.")

        elif history_mode == "expanding":
            if rolling_window_hours is not None:
                raise ValueError(f"{variant['model_id']}: expanding must not define a rolling window.")

            if retraining_interval_hours is None or retraining_interval_hours < 1:
                raise ValueError(f"{variant['model_id']}: retraining_interval_hours must be at least 1.")

        elif history_mode == "rolling":
            if rolling_window_hours is None or rolling_window_hours < 1:
                raise ValueError(f"{variant['model_id']}: rolling_window_hours must be at least 1.")

            if retraining_interval_hours is None or retraining_interval_hours < 1:
                raise ValueError(f"{variant['model_id']}: retraining_interval_hours must be at least 1.")

        else:
            raise ValueError(f"Unsupported history mode: {history_mode}.")

    first_origin = evaluation_targets.index[0]
    last_origin = evaluation_targets.index[-1] - pd.Timedelta(hours=horizon_hours - 1)

    if last_origin < first_origin:
        raise ValueError("Evaluation split contains no complete forecast horizon.")

    forecast_origins = pd.date_range(
        start=first_origin, end=last_origin, freq=f"{forecast_origin_step_hours}h"
    )

    complete_history = pd.concat([fixed_history, evaluation_targets])
    prophet_states: dict[str, tuple[Prophet, pd.Timestamp, pd.Series]] = {}
    forecast_outputs: list[pd.DataFrame] = []

    for forecast_origin in forecast_origins:
        target_index = pd.date_range(start=forecast_origin, periods=horizon_hours, freq=frequency)
        available_history = complete_history.loc[complete_history.index < forecast_origin]

        target_values = evaluation_targets.loc[target_index]
        target_imputed = evaluation_imputation_mask.loc[target_index]
        target_eligible = target_values.notna() & ~target_imputed

        target_exclusion_reason = pd.Series(None, index=target_index, dtype="object")
        target_exclusion_reason.loc[target_imputed] = "target_imputed"
        target_exclusion_reason.loc[target_values.isna()] = "missing_target"

        for model_id in baseline_model_ids:
            raw_predictions = _BASELINE_BUILDERS[model_id](available_history, target_index)

            predictions = (
                raw_predictions.clip(lower=0.0)
                if clip_negative_forecasts
                else raw_predictions.copy()
            )

            model_forecast = pd.DataFrame(
                {
                    "y_pred": predictions,
                    "y_pred_raw": raw_predictions,
                    "y_lower": np.nan,
                    "y_upper": np.nan,
                },
                index=target_index,
            )

            forecast_outputs.append(
                _build_forecast_output(
                    model_forecast,
                    target_values=target_values,
                    target_imputed=target_imputed,
                    target_eligible=target_eligible,
                    target_exclusion_reason=target_exclusion_reason,
                    run_id=run_id,
                    experiment_id=experiment_id,
                    scenario_id=scenario_id,
                    split=split,
                    model_id=model_id,
                    seasonality_config="not_applicable",
                    forecast_origin=forecast_origin,
                    history_mode="expanding",
                    history=available_history,
                    retrained=False,
                    refit_runtime_seconds=0.0,
                    config_version=config_version,
                )
            )

        for variant in prophet_variants:
            model_id = variant["model_id"]
            history_mode = variant["history_mode"]
            retraining_interval_hours = variant["retraining_interval_hours"]

            state = prophet_states.get(model_id)
            had_fitted_model = state is not None
            fit_required = not had_fitted_model

            if state is not None and history_mode != "fixed_train":
                _, fitted_at_origin, _ = state

                if retraining_interval_hours is None:
                    raise RuntimeError(f"{model_id} has no retraining interval.")

                elapsed_hours = (forecast_origin - fitted_at_origin) / pd.Timedelta(hours=1)

                fit_required = elapsed_hours >= retraining_interval_hours

            refit_runtime_seconds = 0.0

            if fit_required:
                model_history = select_prophet_history(
                    fixed_history,
                    available_history,
                    forecast_origin=forecast_origin,
                    history_mode=history_mode,
                    rolling_window_hours=variant["rolling_window_hours"],
                )

                fit_start = pd.Timestamp.now()

                model = fit_prophet_model(
                    model_history,
                    growth=growth,
                    daily_seasonality=daily_seasonality,
                    weekly_seasonality=variant["weekly_seasonality"],
                    yearly_seasonality=yearly_seasonality,
                    country_holidays=country_holidays,
                    local_timezone=local_timezone,
                    log_transform=log_transform,
                    interval_width=interval_width,
                    uncertainty_samples=uncertainty_samples,
                )

                refit_runtime_seconds = (pd.Timestamp.now() - fit_start).total_seconds()

                state = (model, forecast_origin, model_history)
                prophet_states[model_id] = state

            if state is None:
                raise RuntimeError(f"No fitted model exists for {model_id}.")

            model, _, model_history = state

            model_forecast = build_prophet_forecast(
                model,
                target_index,
                clip_negative_forecasts=clip_negative_forecasts,
                history_end=model_history.index[-1],
                local_timezone=local_timezone,
                log_transform=log_transform,
            )

            seasonality_config = (
                f"daily={daily_seasonality};"
                f"weekly={variant['weekly_seasonality']};"
                f"yearly={yearly_seasonality};"
                f"holidays={country_holidays};"
                f"tz={local_timezone};"
                f"log={log_transform}"
            )

            forecast_outputs.append(
                _build_forecast_output(
                    model_forecast,
                    target_values=target_values,
                    target_imputed=target_imputed,
                    target_eligible=target_eligible,
                    target_exclusion_reason=target_exclusion_reason,
                    run_id=run_id,
                    experiment_id=experiment_id,
                    scenario_id=scenario_id,
                    split=split,
                    model_id=model_id,
                    seasonality_config=seasonality_config,
                    forecast_origin=forecast_origin,
                    history_mode=history_mode,
                    history=model_history,
                    retrained=fit_required and had_fitted_model,
                    refit_runtime_seconds=refit_runtime_seconds,
                    config_version=config_version,
                )
            )

    forecasts = pd.concat(forecast_outputs, ignore_index=True)
    forecasts = forecasts[FORECAST_OUTPUT_COLUMNS]

    validate_forecast_output(forecasts, horizon_hours=horizon_hours)

    expected_model_count = len(model_ids)
    models_per_target = forecasts.groupby(
        ["forecast_origin", "target_timestamp"]
    )["model_id"].nunique()

    if not models_per_target.eq(expected_model_count).all():
        raise ValueError("Forecast variants do not use identical forecast origins and targets.")

    return forecasts


def select_prophet_history(
    fixed_history: pd.Series,
    available_history: pd.Series,
    *,
    forecast_origin: pd.Timestamp,
    history_mode: Literal["fixed_train", "expanding", "rolling"],
    rolling_window_hours: int | None,
) -> pd.Series:
    if history_mode == "fixed_train":
        return fixed_history

    if history_mode == "expanding":
        return available_history

    if rolling_window_hours is None:
        raise ValueError("rolling_window_hours is required for rolling history.")

    history_start = forecast_origin - pd.Timedelta(hours=rolling_window_hours)
    return available_history.loc[available_history.index >= history_start]


def _build_forecast_output(
    model_forecast: pd.DataFrame,
    *,
    target_values: pd.Series,
    target_imputed: pd.Series,
    target_eligible: pd.Series,
    target_exclusion_reason: pd.Series,
    run_id: str,
    experiment_id: str,
    scenario_id: str | None,
    split: str,
    model_id: str,
    seasonality_config: str,
    forecast_origin: pd.Timestamp,
    history_mode: str,
    history: pd.Series,
    retrained: bool,
    refit_runtime_seconds: float,
    config_version: str,
) -> pd.DataFrame:
    output = model_forecast.copy()
    output.index.name = "target_timestamp"
    output = output.reset_index()

    output["run_id"] = run_id
    output["experiment_id"] = experiment_id
    output["scenario_id"] = scenario_id
    output["split"] = split
    output["model_id"] = model_id
    output["seasonality_config"] = seasonality_config
    output["forecast_origin"] = forecast_origin
    output["horizon_step"] = np.arange(1, len(output) + 1)

    output["y_true"] = target_values.to_numpy(dtype="float64")
    output["target_eligible"] = target_eligible.to_numpy(dtype=bool)
    output["target_exclusion_reason"] = target_exclusion_reason.to_numpy()
    output["target_imputed"] = target_imputed.to_numpy(dtype=bool)

    output["history_mode"] = history_mode
    output["history_hours"] = len(history)
    output["history_observation_count"] = int(history.notna().sum())
    output["history_start"] = history.index[0]
    output["history_end"] = history.index[-1]

    output["retrained"] = retrained
    output["refit_runtime_seconds"] = refit_runtime_seconds
    output["event_id"] = None
    output["steps_since_event"] = np.nan
    output["config_version"] = config_version

    return output[FORECAST_OUTPUT_COLUMNS]


def _validate_hourly_series(series: pd.Series, name: str, frequency: str) -> None:
    if not isinstance(series, pd.Series):
        raise TypeError(f"{name} must be a pandas Series.")

    if series.empty:
        raise ValueError(f"{name} must not be empty.")

    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must be a DatetimeIndex.")

    if series.index.has_duplicates:
        raise ValueError(f"{name} contains duplicate timestamps.")

    if not series.index.is_monotonic_increasing:
        raise ValueError(f"{name} must be sorted chronologically.")

    if str(series.index.tz) != "UTC":
        raise ValueError(f"{name} must use UTC.")

    expected_index = pd.date_range(start=series.index[0], periods=len(series), freq=frequency)

    if not series.index.equals(expected_index):
        raise ValueError(f"{name} must contain a continuous index at the configured frequency.")

    try:
        values = pd.to_numeric(series, errors="raise").to_numpy(dtype="float64")
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must contain numeric values.") from error

    if np.isinf(values).any():
        raise ValueError(f"{name} contains infinite values.")


def _validate_walk_forward_data(
    fixed_history: pd.Series,
    evaluation_targets: pd.Series,
    evaluation_imputation_mask: pd.Series,
    frequency: str,
) -> None:
    for name, series in {
        "fixed_history": fixed_history,
        "evaluation_targets": evaluation_targets,
    }.items():
        _validate_hourly_series(series, name, frequency)

    expected_evaluation_start = fixed_history.index[-1] + pd.Timedelta(hours=1)

    if evaluation_targets.index[0] != expected_evaluation_start:
        raise ValueError("evaluation_targets must start exactly one hour after fixed_history ends.")

    if not isinstance(evaluation_imputation_mask, pd.Series):
        raise TypeError("evaluation_imputation_mask must be a pandas Series.")

    if not evaluation_imputation_mask.index.equals(evaluation_targets.index):
        raise ValueError("evaluation_imputation_mask must use exactly the evaluation target index.")

    if evaluation_imputation_mask.isna().any():
        raise ValueError("evaluation_imputation_mask contains missing values.")

    if not pd.api.types.is_bool_dtype(evaluation_imputation_mask.dtype):
        raise TypeError("evaluation_imputation_mask must contain booleans.")

