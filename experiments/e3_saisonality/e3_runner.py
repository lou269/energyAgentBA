# conda activate forecasting-env
# python -m experiments.e3_saisonality.e3_runner

import logging
from dataclasses import asdict
from time import perf_counter

import numpy as np
import pandas as pd

from src.common.target_series import read_preprocessed_target
from src.common.timestamps import local_midnight_utc
from src.config.project_config import ProjectConfig
from src.forecasting.forecast_run_manifest import build_forecast_run_manifest
from src.forecasting.forecasting import run_forecast_comparison
from src.pipeline.io import (
    create_experiment_run,
    df_to_csv,
    save_json,
    user_output_directory,
)

from experiments.e3_saisonality.e3_config import SeasonalityExperimentConfig

logger = logging.getLogger(__name__)

_METEOROLOGICAL_SEASON = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
}


def run() -> None:
    run_started = perf_counter()

    project_config = ProjectConfig()
    e3_config = SeasonalityExperimentConfig()
    np.random.seed(e3_config.seed)

    test_window_start = local_midnight_utc(
        e3_config.data.test_window_start_date, project_config.timezone
    )
    test_window_end = local_midnight_utc(
        e3_config.data.test_window_end_date, project_config.timezone
    )

    target_series, target_imputed, _target_value_implausible = read_preprocessed_target(
        project_config
    )
    canonical_manifest = pd.read_csv(
        project_config.canonical_output_dir / "canonical_manifest.csv"
    )
    candidate_id = str(canonical_manifest.iloc[0]["candidate_id"])

    fixed_history = target_series.loc[target_series.index < test_window_start]
    evaluation_window = (target_series.index >= test_window_start) & (
        target_series.index < test_window_end
    )
    evaluation_targets = target_series.loc[evaluation_window]
    evaluation_imputation_mask = target_imputed.loc[evaluation_window]

    prophet_variants = e3_config.prophet_variants
    variant_ids = tuple(variant.model_id for variant in e3_config.prophet_variants)

    run_directory, raw_directory = create_experiment_run(
        project_config.e3_output_dir,
        "e3",
        {"e3_config": asdict(e3_config)},
    )
    run_id = run_directory.name

    forecasts, evaluation_results = run_forecast_comparison(
        (*e3_config.baseline_model_ids, *prophet_variants),
        fixed_history,
        evaluation_targets,
        evaluation_imputation_mask,
        run_id=run_id,
        experiment_id=e3_config.experiment_id,
        split=e3_config.split,
        horizon_days=e3_config.horizon_days,
        forecast_origin_step_days=e3_config.forecast_origin_step_days,
        frequency=e3_config.frequency,
        local_timezone=project_config.timezone,
        clip_negative_forecasts=(e3_config.negative_forecast_handling == "clip_zero"),
        config_version=e3_config.config_version,
        growth=e3_config.growth,
        daily_seasonality=e3_config.daily_seasonality,
        country_holidays=e3_config.country_holidays,
        log_transform=e3_config.log_transform,
        interval_width=e3_config.interval_width,
        uncertainty_samples=e3_config.uncertainty_samples,
        comparison_model_ids=variant_ids,
        reference_model_ids=e3_config.baseline_model_ids,
        nominal_interval_level=e3_config.interval_width,
        mape_min_eligible_watts=e3_config.mape_min_eligible_watts,
    )

    df_to_csv(forecasts, raw_directory, "forecasts")

    for name, result in evaluation_results.items():
        df_to_csv(result, raw_directory, name)

    # Testfrage ist der Unterschied zwischen den Jahreszeiten, dafür reicht overall_metrics allein nicht
    origin_metrics = evaluation_results["origin_metrics"]
    origin_metrics = origin_metrics.assign(
        season=pd.to_datetime(origin_metrics["forecast_day"]).dt.month.map(
            _METEOROLOGICAL_SEASON
        )
    )
    seasonal_breakdown = origin_metrics.groupby(
        ["model_id", "season"], as_index=False
    ).agg(
        mae_w=("mae_w", "mean"),
        rmse_w=("rmse_w", "mean"),
        mape_pct=("mape_pct", "mean"),
    )
    output_directory = user_output_directory(run_directory)
    df_to_csv(seasonal_breakdown, output_directory, "seasonal_breakdown")

    manifest = build_forecast_run_manifest(
        project_root=project_config.project_root,
        run_id=run_id,
        experiment_id=e3_config.experiment_id,
        split=e3_config.split,
        candidate_id=candidate_id,
        config_values={
            "test_window_start": str(test_window_start),
            "test_window_end": str(test_window_end),
        },
        input_paths={
            "canonical_manifest": project_config.canonical_output_dir
            / "canonical_manifest.csv",
            "canonical_data_hourly": project_config.canonical_output_dir
            / "canonical_data_hourly.csv",
            "canonical_quality_hourly": project_config.canonical_output_dir
            / "canonical_quality_hourly.csv",
        },
        output_paths={
            "forecasts": raw_directory / "forecasts.csv",
            "seasonal_breakdown": output_directory / "seasonal_breakdown.csv",
            **{name: raw_directory / f"{name}.csv" for name in evaluation_results},
        },
        split_boundaries={
            "fixed_history_start": fixed_history.index[0],
            "fixed_history_end": fixed_history.index[-1],
            "test_window_start": test_window_start,
            "test_window_end": test_window_end,
            "first_forecast_origin": forecasts["forecast_origin"].min(),
        },
        forecast_origins=tuple(
            forecasts["forecast_origin"].drop_duplicates().sort_values()
        ),
        model_parameters={
            "variants": [
                {
                    "model_id": v.model_id,
                    "history_mode": v.history_mode,
                    "retraining_interval_days": v.retraining_interval_days,
                }
                for v in e3_config.prophet_variants
            ]
        },
        seasonalities={
            v.model_id: {
                "daily": e3_config.daily_seasonality,
                "weekly": v.weekly_seasonality,
                "yearly": v.yearly_seasonality,
            }
            for v in e3_config.prophet_variants
        },
        history_rules={
            "retraining_interval_days": e3_config.prophet_variants[
                0
            ].retraining_interval_days
        },
        metric_definitions={
            "metrics": ["mae", "rmse", "mape"],
            "primary_metric": "mae",
            "mape_positive_targets_only": True,
        },
        exclusion_rules={
            "exclude_imputed_targets": True,
            "complete_horizons_only": True,
        },
        primary_naive_reference=None,
        seed=e3_config.seed,
        uncertainty_samples=e3_config.uncertainty_samples,
        runtime_seconds=perf_counter() - run_started,
    )

    save_json(manifest, raw_directory / "run_manifest.json")

    overall = evaluation_results["overall_metrics"]
    logger.info("E3 Teilfrage 1 abgeschlossen:\n%s", overall.to_string(index=False))
    logger.info("Seasonal breakdown:\n%s", seasonal_breakdown.to_string(index=False))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
