import pandas as pd

from src.forecasting.evaluation import evaluate_forecasts
from src.forecasting.walk_forward import ProphetVariantParameters, build_walk_forward_forecasts


def run_forecast_comparison(
    candidates: tuple[str | ProphetVariantParameters, ...],
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
    local_timezone: str,
    clip_negative_forecasts: bool,
    config_version: str,
    growth: str,
    daily_seasonality: bool,
    country_holidays: str | None,
    log_transform: bool,
    interval_width: float,
    uncertainty_samples: int,
    comparison_model_ids: tuple[str, ...],
    reference_model_ids: tuple[str, ...],
    nominal_interval_level: float,
    mape_min_eligible_watts: float,
    initial_history_start: pd.Timestamp | None = None,
    scenario_id: str | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    if not candidates:
        raise ValueError("candidates must not be empty.")

    
    forecast_frames = [
        build_walk_forward_forecasts(
            fixed_history,
            evaluation_targets,
            evaluation_imputation_mask,
            run_id=run_id,
            experiment_id=experiment_id,
            split=split,
            horizon_hours=horizon_hours,
            forecast_origin_step_hours=forecast_origin_step_hours,
            frequency=frequency,
            local_timezone=local_timezone,
            clip_negative_forecasts=clip_negative_forecasts,
            config_version=config_version,
            baseline_model_id=candidate if isinstance(candidate, str) else None,
            prophet_variant=None if isinstance(candidate, str) else candidate,
            growth=growth,
            daily_seasonality=daily_seasonality,
            country_holidays=country_holidays,
            log_transform=log_transform,
            interval_width=interval_width,
            uncertainty_samples=uncertainty_samples,
            initial_history_start=initial_history_start,
            scenario_id=scenario_id,
        )
        for candidate in candidates
    ]

    forecasts = pd.concat(forecast_frames, ignore_index=True)

    evaluation_results = evaluate_forecasts(
        forecasts,
        horizon_hours=horizon_hours,
        comparison_model_ids=comparison_model_ids,
        reference_model_ids=reference_model_ids,
        nominal_interval_level=nominal_interval_level,
        mape_min_eligible_watts=mape_min_eligible_watts,
    )

    return forecasts, evaluation_results