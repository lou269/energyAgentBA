# conda activate forecasting-env
# python -m experiments.proposal_experiments.e3_saisonality.e3_runner

import logging
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from src.common.target_series import read_preprocessed_target
from src.common.timestamps import parse_utc_timestamp
from src.config.project_config import ProjectConfig
from src.forecasting.evaluation import evaluate_forecasts
from src.forecasting.forecast_run_manifest import build_forecast_run_manifest
from src.forecasting.walk_forward import build_walk_forward_forecasts
from src.pipeline.io import df_to_csv, save_json

from experiments.proposal_experiments.e_config import SeasonalityExperimentConfig

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"

_METEOROLOGICAL_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


def run() -> None:
    run_started = perf_counter()

    project_config = ProjectConfig()
    e3_config = SeasonalityExperimentConfig()
    np.random.seed(e3_config.seed)

    test_window_start = parse_utc_timestamp(e3_config.data.test_window_start, "test_window_start")
    test_window_end = parse_utc_timestamp(e3_config.data.test_window_end, "test_window_end")

    target_series, target_imputed, _target_value_implausible = read_preprocessed_target(project_config)
    canonical_manifest = pd.read_csv(project_config.canonical_output_dir / "canonical_manifest.csv")
    candidate_id = str(canonical_manifest.iloc[0]["candidate_id"])

    fixed_history = target_series.loc[:test_window_start - pd.Timedelta(hours=1)]
    evaluation_targets = target_series.loc[test_window_start:test_window_end]
    evaluation_imputation_mask = target_imputed.loc[test_window_start:test_window_end]

    prophet_variants = e3_config.prophet_variants
    variant_ids = tuple(variant.model_id for variant in e3_config.prophet_variants)

    run_id = "e3_seasonality"

    forecasts = build_walk_forward_forecasts(
        fixed_history=fixed_history,
        evaluation_targets=evaluation_targets,
        evaluation_imputation_mask=evaluation_imputation_mask,
        run_id=run_id,
        experiment_id=e3_config.experiment_id,
        split=e3_config.split,
        horizon_hours=e3_config.horizon_hours,
        forecast_origin_step_hours=e3_config.forecast_origin_step_hours,
        frequency=e3_config.frequency,
        baseline_model_ids=e3_config.baseline_model_ids,
        prophet_variants=prophet_variants,
        growth=e3_config.growth,
        daily_seasonality=e3_config.daily_seasonality,
        country_holidays=e3_config.country_holidays,
        local_timezone=project_config.timezone,
        log_transform=e3_config.log_transform,
        interval_width=e3_config.interval_width,
        clip_negative_forecasts=(e3_config.negative_forecast_handling == "clip_zero"),
        uncertainty_samples=e3_config.uncertainty_samples,
        config_version=e3_config.config_version,
    )

    evaluation_results = evaluate_forecasts(
        forecasts,
        horizon_hours=e3_config.horizon_hours,
        comparison_model_ids=variant_ids,
        reference_model_ids=e3_config.baseline_model_ids,
        nominal_interval_level=e3_config.interval_width,
        mape_min_eligible_watts=e3_config.mape_min_eligible_watts,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_to_csv(forecasts, OUTPUT_DIR, "forecasts")

    for name, result in evaluation_results.items():
        df_to_csv(result, OUTPUT_DIR, name)

    # Testfrage ist der Unterschied zwischen den Jahreszeiten, dafür reicht overall_metrics allein nicht
    origin_metrics = evaluation_results["origin_metrics"]
    origin_metrics = origin_metrics.assign(season=origin_metrics["forecast_origin"].dt.month.map(_METEOROLOGICAL_SEASON))
    seasonal_breakdown = (
        origin_metrics.groupby(["model_id", "season"], as_index=False)
        .agg(mae_w=("mae_w", "mean"), rmse_w=("rmse_w", "mean"), mape_pct=("mape_pct", "mean"))
    )
    df_to_csv(seasonal_breakdown, OUTPUT_DIR, "seasonal_breakdown")

    manifest = build_forecast_run_manifest(
        project_root=project_config.project_root,
        run_id=run_id,
        experiment_id=e3_config.experiment_id,
        split=e3_config.split,
        candidate_id=candidate_id,
        config_values={"test_window_start": str(test_window_start), "test_window_end": str(test_window_end)},
        input_paths={
            "canonical_manifest": project_config.canonical_output_dir / "canonical_manifest.csv",
            "canonical_data_hourly": project_config.canonical_output_dir / "canonical_data_hourly.csv",
            "canonical_quality_hourly": project_config.canonical_output_dir / "canonical_quality_hourly.csv",
        },
        output_paths={
            "forecasts": OUTPUT_DIR / "forecasts.csv",
            "seasonal_breakdown": OUTPUT_DIR / "seasonal_breakdown.csv",
            **{name: OUTPUT_DIR / f"{name}.csv" for name in evaluation_results},
        },
        split_boundaries={
            "fixed_history_start": fixed_history.index[0],
            "fixed_history_end": fixed_history.index[-1],
            "test_window_start": test_window_start,
            "test_window_end": test_window_end,
            "first_forecast_origin": forecasts["forecast_origin"].min(),
        },
        forecast_origins=tuple(forecasts["forecast_origin"].drop_duplicates().sort_values()),
        model_parameters={"variants": [
            {
                "model_id": v.model_id,
                "history_mode": v.history_mode,
                "retraining_interval_hours": v.retraining_interval_hours,
            }
            for v in e3_config.prophet_variants
        ]},
        seasonalities={
            v.model_id: {"daily": e3_config.daily_seasonality, "weekly": v.weekly_seasonality, "yearly": v.yearly_seasonality}
            for v in e3_config.prophet_variants
        },
        history_rules={"retraining_interval_hours": e3_config.prophet_variants[0].retraining_interval_hours},
        metric_definitions={"metrics": ["mae", "rmse", "mape"], "primary_metric": "mae", "mape_positive_targets_only": True},
        exclusion_rules={"exclude_imputed_targets": True, "complete_horizons_only": True},
        primary_naive_reference=None,
        seed=e3_config.seed,
        uncertainty_samples=e3_config.uncertainty_samples,
        runtime_seconds=perf_counter() - run_started,
    )

    save_json(manifest, OUTPUT_DIR / "run_manifest.json")

    overall = evaluation_results["overall_metrics"]
    logger.info("E3 Teilfrage 1 abgeschlossen:\n%s", overall.to_string(index=False))
    logger.info("Sommer/Winter-Aufschlüsselung:\n%s", seasonal_breakdown.to_string(index=False))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
