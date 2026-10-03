import numpy as np
import pandas as pd
from prophet import Prophet

from src.common.timestamps import (
    local_calendar_range,
    local_day_hours,
    shift_local_days,
)
from src.config.config_forecasting import ProphetVariantConfig
from src.forecasting.baselines import (
    build_daily_naive_forecast,
    build_last_value_forecast,
    build_weekly_naive_forecast,
)
from src.forecasting.prophet_model import (
    build_prophet_forecast,
    fit_prophet_model,
    is_refit_required,
    select_prophet_history,
)
from src.forecasting.forecast_schema import (
    FORECAST_OUTPUT_COLUMNS,
    validate_forecast_output,
)


_SEASONAL_NAIVE_BUILDERS = {
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
    horizon_days: int,
    forecast_origin_step_days: int,
    frequency: str,
    local_timezone: str,
    clip_negative_forecasts: bool,
    config_version: str,
    baseline_model_id: str | None = None,
    prophet_variant: ProphetVariantConfig | None = None,
    growth: str = "linear",
    daily_seasonality: bool = True,
    country_holidays: str | None = None,
    log_transform: bool = True,
    interval_width: float = 0.80,
    uncertainty_samples: int = 1000,
    scenario_id: str | None = None,
) -> pd.DataFrame:
    if (baseline_model_id is None) == (prophet_variant is None):
        raise ValueError(
            "Exactly one of baseline_model_id or prophet_variant must be given."
        )

    if baseline_model_id not in (None, "B1", "B2", "B3"):
        raise ValueError(f"Unsupported baseline model ID: {baseline_model_id}")

    _validate_walk_forward_data(
        fixed_history, evaluation_targets, evaluation_imputation_mask, frequency
    )

    for name, value in {
        "run_id": run_id,
        "experiment_id": experiment_id,
        "split": split,
    }.items():
        if not value:
            raise ValueError(f"{name} must not be empty.")

    # Horizont-Scheduling: Ursprünge dürfen sich nicht überlappende Horizonte teilen.
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1.")
    if forecast_origin_step_days < horizon_days:
        raise ValueError(
            "forecast_origin_step_days must be at least horizon_days to prevent overlapping horizons."
        )

    # Prophet-weite Annahmen dieser Implementierung.
    if growth not in ("linear", "flat"):
        raise ValueError("growth must be 'linear' or 'flat'.")
    if not 0.0 < interval_width < 1.0:
        raise ValueError("interval_width must be between 0 and 1.")

    model_id = (
        baseline_model_id if baseline_model_id is not None else prophet_variant.model_id  # type: ignore[union-attr]
    )

    first_origin = evaluation_targets.index[0]
    evaluation_end = evaluation_targets.index[-1] + pd.Timedelta(frequency)
    last_origin = shift_local_days(evaluation_end, -horizon_days, local_timezone)

    if last_origin < first_origin:
        raise ValueError("Evaluation split contains no complete forecast horizon.")

    forecast_origins = local_calendar_range(
        first_origin, forecast_origin_step_days, last_origin, local_timezone
    )

    complete_history = pd.concat([fixed_history, evaluation_targets])
    prophet_state: tuple[Prophet, pd.Timestamp, pd.Series] | None = None
    forecast_outputs: list[pd.DataFrame] = []

    for forecast_origin in forecast_origins:
        target_index = local_day_hours(
            forecast_origin, horizon_days, frequency, local_timezone
        )
        available_history = complete_history.loc[
            complete_history.index < forecast_origin
        ]

        target_values = evaluation_targets.loc[target_index]
        target_imputed = evaluation_imputation_mask.loc[target_index]
        target_eligible = target_values.notna() & ~target_imputed

        target_exclusion_reason = pd.Series(None, index=target_index, dtype="object")
        target_exclusion_reason.loc[target_imputed] = "target_imputed"
        target_exclusion_reason.loc[target_values.isna()] = "missing_target"

        if baseline_model_id is not None:
            if baseline_model_id == "B1":
                raw_predictions = build_last_value_forecast(
                    available_history, target_index
                )
            else:
                raw_predictions = _SEASONAL_NAIVE_BUILDERS[baseline_model_id](
                    available_history, target_index, local_timezone
                )

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
                    local_timezone=local_timezone,
                )
            )

        else:
            assert prophet_variant is not None
            history_mode = prophet_variant.history_mode

            had_fitted_model = prophet_state is not None

            fit_required = is_refit_required(
                had_fitted_model,
                history_mode=history_mode,
                fitted_at=prophet_state[1] if prophet_state is not None else None,
                current_time=forecast_origin,
                retraining_interval_days=prophet_variant.retraining_interval_days,
                local_timezone=local_timezone,
            )

            refit_runtime_seconds = 0.0

            if fit_required:
                model_history = select_prophet_history(
                    fixed_history,
                    available_history,
                    forecast_origin=forecast_origin,
                    history_mode=history_mode,
                    rolling_window_days=prophet_variant.rolling_window_days,
                    local_timezone=local_timezone,
                )

                fit_start = pd.Timestamp.now()

                model = fit_prophet_model(
                    model_history,
                    growth=growth,
                    daily_seasonality=daily_seasonality,
                    weekly_seasonality=prophet_variant.weekly_seasonality,
                    yearly_seasonality=prophet_variant.yearly_seasonality,
                    country_holidays=country_holidays,
                    local_timezone=local_timezone,
                    log_transform=log_transform,
                    interval_width=interval_width,
                    uncertainty_samples=uncertainty_samples,
                )

                refit_runtime_seconds = (pd.Timestamp.now() - fit_start).total_seconds()

                prophet_state = (model, forecast_origin, model_history)

            assert prophet_state is not None

            model, _, model_history = prophet_state

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
                f"weekly={prophet_variant.weekly_seasonality};"
                f"yearly={prophet_variant.yearly_seasonality};"
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
                    local_timezone=local_timezone,
                )
            )

    forecasts = pd.concat(forecast_outputs, ignore_index=True)
    forecasts = forecasts[FORECAST_OUTPUT_COLUMNS]

    validate_forecast_output(forecasts)

    return forecasts


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
    local_timezone: str,
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
    output["forecast_day"] = forecast_origin.tz_convert(local_timezone).date()
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

    expected_index = pd.date_range(
        start=series.index[0], periods=len(series), freq=frequency
    )

    if not series.index.equals(expected_index):
        raise ValueError(
            f"{name} must contain a continuous index at the configured frequency."
        )

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
        raise ValueError(
            "evaluation_targets must start exactly one hour after fixed_history ends."
        )

    if not isinstance(evaluation_imputation_mask, pd.Series):
        raise TypeError("evaluation_imputation_mask must be a pandas Series.")

    if not evaluation_imputation_mask.index.equals(evaluation_targets.index):
        raise ValueError(
            "evaluation_imputation_mask must use exactly the evaluation target index."
        )

    if evaluation_imputation_mask.isna().any():
        raise ValueError("evaluation_imputation_mask contains missing values.")

    if not pd.api.types.is_bool_dtype(evaluation_imputation_mask.dtype):
        raise TypeError("evaluation_imputation_mask must contain booleans.")
