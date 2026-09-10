# conda activate forecasting-env
# python -m experiments.component_studies.k1_preprocessing.k1_runner
#
# Voraussetzung: k1_data_preparation_runner.py wurde vorher in nilmtk-env ausgeführt

from __future__ import annotations

from dataclasses import asdict, replace
import logging
from time import perf_counter
from typing import cast

import pandas as pd

from src.config.forecasting_config import ForecastingConfig
from src.config.preprocessing_config import PreprocessingConfig
from src.config.project_config import ProjectConfig
from src.forecasting.evaluation import evaluate_forecasts, select_primary_naive_reference
from src.forecasting.forecast_run_manifest import build_forecast_run_manifest
from src.forecasting.walk_forward import ProphetVariantParameters, build_walk_forward_forecasts
from src.pipeline.io import df_to_csv, save_json
from src.preprocessing.gap_treatment import apply_gap_treatment

from experiments.component_studies.k1_preprocessing.k1_config import (
    FIXED_VALIDATION_END,
    FIXED_VALIDATION_START,
    K1_OUTPUT_ROOT,
    K1_SCENARIOS,
    K1_VARIANTS,
    k1_scenario_output_dir,
    k1_variant_output_dir,
)

logger = logging.getLogger(__name__)

# Nur B1 (letzter Wert) -- B2/B3 brauchen eine exakte Lag-Referenz (t-24h/t-168h) und wären an den bewusst zugelassenen Datenlücken 
# der größeren Fenster sonst nicht auswertbar. K1 vergleicht sowieso nur C2 über die Varianten, nicht C2 gegen die
# Baselines (das ist K2s Frage) -- B1 bleibt nur als von evaluate_forecasts geforderte Referen ->  build_walk_forward_forecasts kann unverändert
# wiederverwendet werden, keine eigene Schleifenkopie nötig
K1_BASELINE_MODEL_IDS: tuple[str, ...] = ("B1",)


def run() -> None:
    project_config = ProjectConfig()
    preprocessing_config = PreprocessingConfig()
    forecasting_config = ForecastingConfig()

    # C2 (expanding, täglich retraining) -- dieselbe produktive Variante wie in K2, damit der Vergleich hier direkt an das K2-Ergebnis anschliesst. 
    # weekly_seasonality wird pro Szenario überschrieben (-> K1 scenarios), history_mode/retraining bleiben unverändert.
    base_prophet_variant = forecasting_config.selected_prophet_variant

    summary_rows: list[dict] = []

    for variant in K1_VARIANTS:
        logger.info("Preparing K1 variant %s...", variant.variant_id)

        canonical_dir = k1_variant_output_dir(variant.variant_id) / "canonical"

        canonical_manifest = pd.read_csv(
            canonical_dir / "canonical_manifest.csv",
            parse_dates=["window_start", "window_end"],
        )
        candidate_id = str(canonical_manifest.iloc[0]["candidate_id"])
        target_column = str(canonical_manifest.iloc[0]["column_name"])
        meter_key = str(canonical_manifest.iloc[0]["meter_key"])
        train_length_days = float(canonical_manifest.iloc[0]["train_length_days"])

        data_hourly = pd.read_csv(
            canonical_dir / "canonical_data_hourly.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )
        quality_hourly = pd.read_csv(
            canonical_dir / "canonical_quality_hourly.csv",
            parse_dates=["timestamp"],
            index_col="timestamp",
        )

        # Kein anteiliger Split mehr: das Validation-Fenster ist für alle Varianten identisch (FIXED_VALIDATION_START/-END), 
        # nur die Trainingslänge  variiert
        # apply_gap_treatment arbeitet direkt auf dem kompletten Fenster, kein train/val/test-Dreiersplit mötig 
        treated_hourly, imputation_mask_hourly = apply_gap_treatment(
            data_hourly,
            quality_hourly,
            # bleibt für alle Varianten bei 2h -> nicht dasselbe wie max_availability_gap_hours
            max_gap_intervals=preprocessing_config.max_imputation_gap_hourly,
            method=preprocessing_config.gap_treatment_method,
        )

        preprocessing_dir = k1_variant_output_dir(variant.variant_id) / "preprocessing"
        preprocessing_dir.mkdir(parents=True, exist_ok=True)
        df_to_csv(treated_hourly.reset_index(), preprocessing_dir, "treated_hourly")
        df_to_csv(imputation_mask_hourly.reset_index(), preprocessing_dir, "imputation_mask_hourly")

        fixed_history = treated_hourly.loc[:FIXED_VALIDATION_START - pd.Timedelta(hours=1), target_column]
        evaluation_targets = treated_hourly.loc[FIXED_VALIDATION_START:FIXED_VALIDATION_END, target_column]
        evaluation_imputation_mask = imputation_mask_hourly.loc[FIXED_VALIDATION_START:FIXED_VALIDATION_END, meter_key]

        for scenario in K1_SCENARIOS:
            run_started = perf_counter()
            logger.info("Running K1 variant %s / scenario %s...", variant.variant_id, scenario.scenario_id)

            prophet_variant = replace(base_prophet_variant, weekly_seasonality=scenario.weekly_seasonality)
            prophet_variants = (cast(ProphetVariantParameters, asdict(prophet_variant)),)

            run_id = f"k1_{variant.variant_id}_{scenario.scenario_id}"

            forecasts = build_walk_forward_forecasts(
                fixed_history=fixed_history,
                evaluation_targets=evaluation_targets,
                evaluation_imputation_mask=evaluation_imputation_mask,
                run_id=run_id,
                experiment_id="K1_preprocessing",
                split="validation",
                horizon_hours=forecasting_config.horizon_hours,
                forecast_origin_step_hours=forecasting_config.forecast_origin_step_hours,
                baseline_model_ids=K1_BASELINE_MODEL_IDS,
                prophet_variants=prophet_variants,
                growth=forecasting_config.growth,
                daily_seasonality=forecasting_config.daily_seasonality,
                yearly_seasonality=scenario.yearly_seasonality,
                country_holidays=forecasting_config.country_holidays,
                local_timezone=forecasting_config.timezone,
                log_transform=forecasting_config.log_transform,
                interval_width=forecasting_config.interval_width,
                clip_negative_forecasts=(forecasting_config.negative_forecast_handling == "clip_zero"),
                uncertainty_samples=forecasting_config.uncertainty_samples,
                config_version="k1-0.1",
            )

            evaluation_results = evaluate_forecasts(
                forecasts,
                horizon_hours=forecasting_config.horizon_hours,
                comparison_model_ids=(prophet_variant.model_id,),
                reference_model_ids=K1_BASELINE_MODEL_IDS,
                nominal_interval_level=forecasting_config.interval_width,
                mape_min_eligible_watts=forecasting_config.mape_min_eligible_watts,
            )

            primary_naive_reference = select_primary_naive_reference(
                evaluation_results["overall_metrics"],
                K1_BASELINE_MODEL_IDS,
            )

            forecasting_dir = k1_scenario_output_dir(variant.variant_id, scenario.scenario_id) / "forecasting"
            forecasting_dir.mkdir(parents=True, exist_ok=True)

            df_to_csv(forecasts, forecasting_dir, "forecasts")

            for name, result in evaluation_results.items():
                df_to_csv(result, forecasting_dir, name)

            manifest = build_forecast_run_manifest(
                project_root=project_config.project_root,
                run_id=run_id,
                experiment_id="K1_preprocessing",
                split="validation",
                candidate_id=candidate_id,
                config_values={
                    "variant_id": variant.variant_id,
                    "scenario_id": scenario.scenario_id,
                    "max_availability_gap_hours": variant.max_availability_gap_hours,
                    "max_imputation_gap_hourly": preprocessing_config.max_imputation_gap_hourly,
                    "fixed_validation_start": str(FIXED_VALIDATION_START),
                    "fixed_validation_end": str(FIXED_VALIDATION_END),
                },
                input_paths={
                    "canonical_manifest": canonical_dir / "canonical_manifest.csv",
                    "canonical_data_hourly": canonical_dir / "canonical_data_hourly.csv",
                    "canonical_quality_hourly": canonical_dir / "canonical_quality_hourly.csv",
                },
                output_paths={
                    "forecasts": forecasting_dir / "forecasts.csv",
                    **{name: forecasting_dir / f"{name}.csv" for name in evaluation_results},
                },
                split_boundaries={
                    "fixed_history_start": fixed_history.index[0],
                    "fixed_history_end": fixed_history.index[-1],
                    "first_forecast_origin": forecasts["forecast_origin"].min(),
                },
                forecast_origins=tuple(forecasts["forecast_origin"].drop_duplicates().sort_values()),
                model_parameters={
                    "variant_id": variant.variant_id,
                    "scenario_id": scenario.scenario_id,
                    "prophet_model_id": prophet_variant.model_id,
                    "history_mode": prophet_variant.history_mode,
                },
                seasonalities={
                    prophet_variant.model_id: {
                        "daily": forecasting_config.daily_seasonality,
                        "weekly": prophet_variant.weekly_seasonality,
                        "yearly": scenario.yearly_seasonality,
                    }
                },
                history_rules={
                    "history_mode": prophet_variant.history_mode,
                    "retraining_interval_hours": prophet_variant.retraining_interval_hours,
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
                primary_naive_reference=primary_naive_reference,
                seed=forecasting_config.seed,
                uncertainty_samples=forecasting_config.uncertainty_samples,
                runtime_seconds=perf_counter() - run_started,
            )

            save_json(manifest, forecasting_dir / "run_manifest.json")

            overall = evaluation_results["overall_metrics"]
            prophet_row = overall.loc[overall["model_id"].eq(prophet_variant.model_id)].iloc[0]

            summary_rows.append(
                {
                    "variant_id": variant.variant_id,
                    "scenario_id": scenario.scenario_id,
                    "weekly_seasonality": scenario.weekly_seasonality,
                    "yearly_seasonality": scenario.yearly_seasonality,
                    "max_availability_gap_hours": variant.max_availability_gap_hours,
                    "train_length_days": train_length_days,
                    "mae_w": prophet_row["mae_w"],
                    "rmse_w": prophet_row["rmse_w"],
                    "mape_pct": prophet_row["mape_pct"],
                    "evaluated_target_count": prophet_row["evaluated_target_count"],
                    "primary_naive_reference": primary_naive_reference,
                }
            )

            logger.info(
                "Variant %s / scenario %s done: MAE=%.1fW",
                variant.variant_id,
                scenario.scenario_id,
                prophet_row["mae_w"],
            )

    summary = pd.DataFrame(summary_rows)
    K1_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    df_to_csv(summary, K1_OUTPUT_ROOT, "comparison_summary")

    logger.info("K1 comparison completed:\n%s", summary.to_string(index=False))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()