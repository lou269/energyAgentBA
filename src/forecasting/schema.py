from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


FORECAST_OUTPUT_COLUMNS = [
    "run_id",
    "split",
    "model_id",
    "forecast_origin",
    "target_timestamp",
    "horizon_step",
    "y_pred",
    "y_pred_raw",
    "y_lower",
    "y_upper",
    "y_true",
    "target_eligible",
    "target_exclusion_reason",
    "target_imputed",
    "history_mode",
    "history_hours",
    "history_start",
    "history_end",
    "retrained",
    "refit_runtime_seconds",
    "event_id",
    "steps_since_event",
    "config_version",
]

FORECAST_KEY_COLUMNS = [
    "run_id",
    "split",
    "model_id",
    "forecast_origin",
    "target_timestamp",
]

RUN_METADATA_FIELDS = [
    "run_id",
    "config_version",
    "data_version",
    "code_version",
    "candidate_id",
    "split_boundaries",
    "forecast_origins",
    "python_version",
    "prophet_version",
    "model_parameters",
    "seasonalities",
    "history_rules",
    "imputation_rule",
    "eligibility_rule",
    "metric_definitions",
    "primary_naive_reference",
    "event_definition",
    "runtime_seconds",
]


def validate_forecast_output(
    forecasts: pd.DataFrame,
    *,
    horizon_hours: int,
    complete_horizons_only: bool = True,
) -> None:
    """Validiert die zentralen Garantien des Forecast-Artefakts."""

    if horizon_hours < 1:
        raise ValueError("horizon_hours must be at least 1.")

    missing_columns = set(FORECAST_OUTPUT_COLUMNS).difference(
        forecasts.columns
    )

    if missing_columns:
        raise ValueError(
            "Forecast output is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if forecasts.empty:
        raise ValueError("Forecast output must not be empty.")

    required_values = [
        column
        for column in FORECAST_OUTPUT_COLUMNS
        if column
        not in {
            "y_lower",
            "y_upper",
            "y_true",
            "target_exclusion_reason",
            "event_id",
            "steps_since_event",
        }
    ]

    if forecasts[required_values].isna().any().any():
        invalid_columns = forecasts[required_values].columns[
            forecasts[required_values].isna().any()
        ].tolist()

        raise ValueError(
            "Forecast output contains missing required values in: "
            + ", ".join(invalid_columns)
        )

    if forecasts.duplicated(FORECAST_KEY_COLUMNS).any():
        raise ValueError(
            "Forecast output contains duplicate forecast records."
        )

    expected_target_timestamps = (
        forecasts["forecast_origin"]
        + pd.to_timedelta(
            forecasts["horizon_step"] - 1,
            unit="h",
        )
    )

    invalid_time_relation = (
        forecasts["target_timestamp"] != expected_target_timestamps
    )

    if invalid_time_relation.any():
        raise ValueError(
            "target_timestamp does not match forecast_origin and "
            "horizon_step."
        )

    invalid_history = (
        (forecasts["history_hours"] < 1)
        | (forecasts["history_start"] > forecasts["history_end"])
        | (forecasts["history_end"] >= forecasts["forecast_origin"])
    )

    if invalid_history.any():
        raise ValueError(
            "Forecast output contains invalid or non-causal history."
        )

    if complete_horizons_only:
        horizon_summary = forecasts.groupby(
            [
                "run_id",
                "split",
                "model_id",
                "forecast_origin",
            ]
        )["horizon_step"].agg(
            row_count="size",
            unique_steps="nunique",
            first_step="min",
            last_step="max",
        )

        incomplete_horizons = (
            (horizon_summary["row_count"] != horizon_hours)
            | (horizon_summary["unique_steps"] != horizon_hours)
            | (horizon_summary["first_step"] != 1)
            | (horizon_summary["last_step"] != horizon_hours)
        )

        if incomplete_horizons.any():
            raise ValueError(
                "Forecast output contains incomplete horizons."
            )

    interval_mismatch = (
        forecasts["y_lower"].isna()
        != forecasts["y_upper"].isna()
    )

    invalid_intervals = (
        forecasts["y_lower"].notna()
        & (forecasts["y_lower"] > forecasts["y_upper"])
    )

    if interval_mismatch.any() or invalid_intervals.any():
        raise ValueError(
            "Prediction intervals are incomplete or invalid."
        )

    eligible = forecasts["target_eligible"]

    invalid_eligibility = (
        (eligible & forecasts["y_true"].isna())
        | (eligible & forecasts["target_imputed"])
        | (eligible & forecasts["target_exclusion_reason"].notna())
        | (~eligible & forecasts["target_exclusion_reason"].isna())
    )

    if invalid_eligibility.any():
        raise ValueError(
            "Target eligibility, ground truth and exclusion reason "
            "are inconsistent."
        )

    event_mismatch = (
        forecasts["event_id"].isna()
        != forecasts["steps_since_event"].isna()
    )

    if event_mismatch.any():
        raise ValueError(
            "event_id and steps_since_event must be provided together."
        )

    target_metadata = [
        "y_true",
        "target_eligible",
        "target_exclusion_reason",
        "target_imputed",
    ]

    target_consistency = (
        forecasts.groupby(
            ["run_id", "split", "target_timestamp"]
        )[target_metadata]
        .nunique(dropna=False)
        .gt(1)
    )

    if target_consistency.any().any():
        raise ValueError(
            "Models use inconsistent ground truth or eligibility data."
        )


def validate_run_metadata(metadata: Mapping[str, object]) -> None:
    """Prüft die Vollständigkeit der laufbezogenen Metadaten."""

    missing_fields = set(RUN_METADATA_FIELDS).difference(metadata)

    if missing_fields:
        raise ValueError(
            "Run metadata is missing required fields: "
            + ", ".join(sorted(missing_fields))
        )

    runtime_seconds = metadata["runtime_seconds"]

    if not isinstance(runtime_seconds, (int, float)):
        raise TypeError("runtime_seconds must be numeric.")

    if runtime_seconds < 0:
        raise ValueError("runtime_seconds must not be negative.")