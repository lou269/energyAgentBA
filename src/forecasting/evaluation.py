import numpy as np
import pandas as pd

from src.forecasting.forecast_schema import validate_forecast_output


BASE_GROUP_COLUMNS = ["run_id", "split", "model_id"]
ORIGIN_GROUP_COLUMNS = [
    "run_id",
    "split",
    "model_id",
    "forecast_origin",
    "forecast_day",
]
ERROR_METRIC_COLUMNS = ["mae_w", "rmse_w", "mape_pct"]


def evaluate_forecasts(
    forecasts: pd.DataFrame,
    *,
    comparison_model_ids: tuple[str, ...],
    reference_model_ids: tuple[str, ...],
    nominal_interval_level: float,
    mape_min_eligible_watts: float,
) -> dict[str, pd.DataFrame]:
    validate_forecast_output(forecasts)
    _validate_evaluation_input(
        forecasts,
        comparison_model_ids=comparison_model_ids,
        reference_model_ids=reference_model_ids,
    )

    overall_metrics = _calculate_grouped_metrics(
        forecasts, BASE_GROUP_COLUMNS, mape_min_eligible_watts
    )
    overall_metrics = _add_operational_metrics(overall_metrics, forecasts)
    origin_metrics = _calculate_grouped_metrics(
        forecasts, ORIGIN_GROUP_COLUMNS, mape_min_eligible_watts
    )
    horizon_metrics = _calculate_grouped_metrics(
        forecasts, [*BASE_GROUP_COLUMNS, "horizon_step"], mape_min_eligible_watts
    )

    return {
        "overall_metrics": overall_metrics,
        "origin_metrics": origin_metrics,
        "origin_metric_distribution": _calculate_origin_metric_distribution(
            origin_metrics
        ),
        "horizon_metrics": horizon_metrics,
        "paired_origin_differences": _calculate_paired_origin_differences(
            origin_metrics,
            comparison_model_ids=comparison_model_ids,
            reference_model_ids=reference_model_ids,
        ),
        "mae_skill": _calculate_mae_skill(
            overall_metrics,
            comparison_model_ids=comparison_model_ids,
            reference_model_ids=reference_model_ids,
        ),
        "interval_metrics": _calculate_interval_metrics(
            forecasts, nominal_interval_level=nominal_interval_level
        ),
        "target_exclusions": _calculate_target_exclusions(forecasts, overall_metrics),
    }


def select_primary_naive_reference(
    overall_metrics: pd.DataFrame,
    baseline_model_ids: tuple[str, ...],
    *,
    split: str = "validation",
) -> str:
    required_columns = {"run_id", "split", "model_id", "mae_w", "rmse_w"}
    missing_columns = required_columns.difference(overall_metrics.columns)

    if missing_columns:
        raise ValueError(
            "overall_metrics is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if not baseline_model_ids:
        raise ValueError("baseline_model_ids must not be empty.")

    candidates = overall_metrics.loc[
        overall_metrics["split"].eq(split)
        & overall_metrics["model_id"].isin(baseline_model_ids)
    ].copy()

    if candidates.empty:
        raise ValueError(f"No naive baseline metrics found for split {split!r}.")

    if candidates["run_id"].nunique() != 1:
        raise ValueError(
            "Primary naive reference must be selected from exactly one run."
        )

    missing_models = set(baseline_model_ids).difference(candidates["model_id"])

    if missing_models:
        raise ValueError(
            "Naive baseline metrics are missing for: "
            + ", ".join(sorted(missing_models))
        )

    candidates = candidates.sort_values(
        ["mae_w", "rmse_w", "model_id"], na_position="last"
    )

    if pd.isna(candidates.iloc[0]["mae_w"]):
        raise ValueError(
            "Primary naive reference cannot be selected without evaluable targets."
        )

    return str(candidates.iloc[0]["model_id"])


def _validate_evaluation_input(
    forecasts: pd.DataFrame,
    *,
    comparison_model_ids: tuple[str, ...],
    reference_model_ids: tuple[str, ...],
) -> None:
    if not reference_model_ids:
        raise ValueError("reference_model_ids must not be empty.")

    if len(comparison_model_ids) != len(set(comparison_model_ids)):
        raise ValueError("comparison_model_ids must be unique.")

    if len(reference_model_ids) != len(set(reference_model_ids)):
        raise ValueError("reference_model_ids must be unique.")

    required_model_ids = set(comparison_model_ids) | set(reference_model_ids)

    for (run_id, split), group in forecasts.groupby(["run_id", "split"], sort=False):
        available_model_ids: set[str] = set(group["model_id"].to_list())
        missing_model_ids = required_model_ids.difference(available_model_ids)

        if missing_model_ids:
            raise ValueError(
                f"Run {run_id!r}, split {split!r} is missing models: "
                + ", ".join(sorted(missing_model_ids))
            )

    model_counts = (
        forecasts.groupby(["run_id", "split"])["model_id"]
        .nunique()
        .rename("expected_model_count")
        .reset_index()
    )
    target_model_counts = (
        forecasts.groupby(["run_id", "split", "forecast_origin", "target_timestamp"])[
            "model_id"
        ]
        .nunique()
        .rename("actual_model_count")
        .reset_index()
        .merge(model_counts, on=["run_id", "split"], how="left")
    )

    unequal_target_sets = (
        target_model_counts["actual_model_count"]
        != target_model_counts["expected_model_count"]
    )

    if unequal_target_sets.any():
        raise ValueError(
            "Models must use identical forecast origins and target timestamps."
        )

    finite_values = forecasts[
        ["y_pred", "y_pred_raw", "refit_runtime_seconds"]
    ].to_numpy(dtype="float64")

    if not np.isfinite(finite_values).all():
        raise ValueError("Forecast values and refit runtimes must be finite.")

    eligible_truth = forecasts.loc[forecasts["target_eligible"], "y_true"].to_numpy(
        dtype="float64"
    )

    if not np.isfinite(eligible_truth).all():
        raise ValueError("Eligible ground-truth values must be finite.")

    interval_values = forecasts.loc[
        forecasts["y_lower"].notna(), ["y_lower", "y_upper"]
    ].to_numpy(dtype="float64")

    if not np.isfinite(interval_values).all():
        raise ValueError("Available prediction intervals must be finite.")


def _calculate_grouped_metrics(
    forecasts: pd.DataFrame,
    group_columns: list[str],
    mape_min_eligible_watts: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for keys, group in forecasts.groupby(group_columns, sort=True, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row: dict[str, object] = {}

        for column, key in zip(group_columns, keys, strict=True):
            row[column] = key

        row.update(_calculate_error_metrics(group, mape_min_eligible_watts))
        rows.append(row)

    return pd.DataFrame(rows)


def score_cycle_forecast(
    forecast: pd.DataFrame,
    target_series: pd.Series,
    target_imputed: pd.Series | None,
    mape_min_eligible_watts: float,
) -> tuple[float, float]:
    actual, eligible = _actual_and_eligible(forecast, target_series, target_imputed)
    predicted = forecast["y_pred"].to_numpy()

    mae_w = calculate_mae(actual, predicted, eligible)
    mape_pct = calculate_mape(actual, predicted, eligible, mape_min_eligible_watts)

    return mae_w, mape_pct


def score_daily_means(
    forecasts: pd.DataFrame,
    actual_daily_mean_w: pd.Series,
    *,
    group_column: str,
    day_column: str,
) -> pd.DataFrame:
    # Tagesmittel der Prognose gegen das Ist-Tagesmittel je Tag, day_error_w gemittelt ist der Tages-MAE
    # -> actual_daily_mean_w hat day_column als Index
    predicted_w = forecasts.groupby([group_column, day_column])["y_pred"].mean()
    actual_w = actual_daily_mean_w.reindex(
        predicted_w.index.get_level_values(day_column)
    ).to_numpy()
    bias_w = predicted_w - actual_w

    return pd.DataFrame(
        {
            "predicted_w": predicted_w,
            "actual_w": actual_w,
            "day_bias_w": bias_w,
            "day_error_w": bias_w.abs(),
        }
    ).reset_index()


def _actual_and_eligible(
    forecast: pd.DataFrame,
    target_series: pd.Series,
    target_imputed: pd.Series | None,
) -> tuple[np.ndarray, np.ndarray]:
    actual = target_series.reindex(forecast["target_timestamp"])

    # ffill-imputierte Zielstunden zählen nicht, gleiche Regel wie target_eligible
    eligible = actual.notna().to_numpy()
    if target_imputed is not None:
        imputed = (
            target_imputed.reindex(actual.index).fillna(False).to_numpy(dtype=bool)
        )
        eligible = eligible & ~imputed

    return actual.to_numpy(), eligible


def calculate_mae(
    y_true: np.ndarray, y_pred: np.ndarray, eligible: np.ndarray
) -> float:
    if not eligible.any():
        return float("nan")

    errors = y_pred[eligible] - y_true[eligible]
    return float(np.mean(np.abs(errors)))


def calculate_mape(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eligible: np.ndarray,
    mape_min_eligible_watts: float,
) -> float:
    mape_eligible = eligible & (y_true > mape_min_eligible_watts)

    if not mape_eligible.any():
        return float("nan")

    absolute_percentage_errors = np.abs(
        (y_pred[mape_eligible] - y_true[mape_eligible]) / y_true[mape_eligible]
    )
    return float(np.mean(absolute_percentage_errors) * 100)


def _calculate_error_metrics(
    forecasts: pd.DataFrame,
    mape_min_eligible_watts: float,
) -> dict[str, int | float]:
    possible_count = len(forecasts)
    eligible = forecasts["target_eligible"]
    evaluated = forecasts.loc[eligible]

    evaluated_count = len(evaluated)
    excluded_count = possible_count - evaluated_count

    mae = calculate_mae(
        forecasts["y_true"].to_numpy(dtype="float64"),
        forecasts["y_pred"].to_numpy(dtype="float64"),
        eligible.to_numpy(),
    )

    if evaluated.empty:
        rmse = np.nan
    else:
        errors = evaluated["y_pred"].to_numpy(dtype="float64") - evaluated[
            "y_true"
        ].to_numpy(dtype="float64")
        rmse = float(np.sqrt(np.mean(np.square(errors))))

    mape_eligible = eligible & forecasts["y_true"].gt(mape_min_eligible_watts)
    mape_count = int(mape_eligible.sum())

    mape = calculate_mape(
        forecasts["y_true"].to_numpy(dtype="float64"),
        forecasts["y_pred"].to_numpy(dtype="float64"),
        eligible.to_numpy(),
        mape_min_eligible_watts,
    )

    negative_count = int(forecasts["y_pred_raw"].lt(0).sum())

    interval_available_count = int(forecasts["y_lower"].notna().sum())
    negative_interval_lower_count = int(forecasts["y_lower"].lt(0).sum())

    return {
        "possible_target_count": possible_count,
        "evaluated_target_count": evaluated_count,
        "excluded_target_count": excluded_count,
        "target_exclusion_share": excluded_count / possible_count,
        "mae_w": mae,
        "rmse_w": rmse,
        "mape_pct": mape,
        "mape_target_count": mape_count,
        "mape_excluded_target_count": possible_count - mape_count,
        "mape_non_positive_target_count": int(
            (eligible & forecasts["y_true"].le(0)).sum()
        ),
        "mape_below_floor_target_count": int(
            (
                eligible
                & forecasts["y_true"].gt(0)
                & forecasts["y_true"].le(mape_min_eligible_watts)
            ).sum()
        ),
        "negative_forecast_count": negative_count,
        "negative_forecast_share": negative_count / possible_count,
        "negative_interval_lower_count": negative_interval_lower_count,
        "negative_interval_lower_share": (
            negative_interval_lower_count / interval_available_count
            if interval_available_count > 0
            else np.nan
        ),
    }


def _add_operational_metrics(
    overall_metrics: pd.DataFrame,
    forecasts: pd.DataFrame,
) -> pd.DataFrame:
    per_origin = forecasts.groupby(ORIGIN_GROUP_COLUMNS, as_index=False).agg(
        retrained=("retrained", "first"),
        refit_runtime_seconds=("refit_runtime_seconds", "first"),
    )
    operational_metrics = per_origin.groupby(BASE_GROUP_COLUMNS, as_index=False).agg(
        forecast_origin_count=("forecast_origin", "size"),
        retraining_count=("retrained", "sum"),
        total_refit_runtime_seconds=("refit_runtime_seconds", "sum"),
    )
    operational_metrics["retraining_count"] = operational_metrics[
        "retraining_count"
    ].astype("int64")

    return overall_metrics.merge(
        operational_metrics,
        on=BASE_GROUP_COLUMNS,
        how="left",
        validate="one_to_one",
    )


def _calculate_origin_metric_distribution(
    origin_metrics: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for keys, group in origin_metrics.groupby(BASE_GROUP_COLUMNS, sort=True):
        metadata = dict(zip(BASE_GROUP_COLUMNS, keys, strict=True))

        for metric in ERROR_METRIC_COLUMNS:
            values = group[metric].dropna()
            first_quartile = values.quantile(0.25)
            third_quartile = values.quantile(0.75)

            rows.append(
                {
                    **metadata,
                    "metric": metric,
                    "origin_count": len(values),
                    "median": values.median(),
                    "first_quartile": first_quartile,
                    "third_quartile": third_quartile,
                    "interquartile_range": third_quartile - first_quartile,
                }
            )

    return pd.DataFrame(rows)


def _calculate_paired_origin_differences(
    origin_metrics: pd.DataFrame,
    *,
    comparison_model_ids: tuple[str, ...],
    reference_model_ids: tuple[str, ...],
) -> pd.DataFrame:
    key_columns = ["run_id", "split", "forecast_origin", "forecast_day"]
    difference_columns = [f"{metric}_difference" for metric in ERROR_METRIC_COLUMNS]

    output_columns = [
        *key_columns,
        "model_id",
        "reference_model_id",
        *difference_columns,
    ]

    result_frames: list[pd.DataFrame] = []

    comparisons = origin_metrics.loc[
        origin_metrics["model_id"].isin(comparison_model_ids)
    ]

    for reference_model_id in reference_model_ids:
        reference = origin_metrics.loc[
            origin_metrics["model_id"].eq(reference_model_id),
            [*key_columns, *ERROR_METRIC_COLUMNS],
        ].rename(
            columns={metric: f"reference_{metric}" for metric in ERROR_METRIC_COLUMNS}
        )

        paired = comparisons.loc[comparisons["model_id"].ne(reference_model_id)].merge(
            reference,
            on=key_columns,
            how="inner",
            validate="many_to_one",
        )
        paired["reference_model_id"] = reference_model_id

        for metric in ERROR_METRIC_COLUMNS:
            paired[f"{metric}_difference"] = (
                paired[metric] - paired[f"reference_{metric}"]
            )

        result_frames.append(paired[output_columns])

    if not result_frames:
        return pd.DataFrame(columns=output_columns)

    return (
        pd.concat(result_frames, ignore_index=True)
        .sort_values(
            [
                "run_id",
                "split",
                "model_id",
                "reference_model_id",
                "forecast_origin",
            ]
        )
        .reset_index(drop=True)
    )


def _calculate_mae_skill(
    overall_metrics: pd.DataFrame,
    *,
    comparison_model_ids: tuple[str, ...],
    reference_model_ids: tuple[str, ...],
) -> pd.DataFrame:
    key_columns = ["run_id", "split"]
    output_columns = [
        *key_columns,
        "model_id",
        "reference_model_id",
        "mae_w",
        "reference_mae_w",
        "mae_skill",
    ]
    result_frames: list[pd.DataFrame] = []

    comparisons = overall_metrics.loc[
        overall_metrics["model_id"].isin(comparison_model_ids),
        [*key_columns, "model_id", "mae_w"],
    ]

    for reference_model_id in reference_model_ids:
        reference = overall_metrics.loc[
            overall_metrics["model_id"].eq(reference_model_id), [*key_columns, "mae_w"]
        ].rename(columns={"mae_w": "reference_mae_w"})

        skill = comparisons.loc[comparisons["model_id"].ne(reference_model_id)].merge(
            reference,
            on=key_columns,
            how="inner",
            validate="many_to_one",
        )
        skill["reference_model_id"] = reference_model_id

        skill["mae_skill"] = np.where(
            skill["reference_mae_w"].gt(0),
            1 - skill["mae_w"] / skill["reference_mae_w"],
            np.nan,
        )

        result_frames.append(skill[output_columns])

    if not result_frames:
        return pd.DataFrame(columns=output_columns)

    return (
        pd.concat(result_frames, ignore_index=True)
        .sort_values(["run_id", "split", "model_id", "reference_model_id"])
        .reset_index(drop=True)
    )


def _calculate_interval_metrics(
    forecasts: pd.DataFrame,
    *,
    nominal_interval_level: float,
) -> pd.DataFrame:
    columns = [
        *BASE_GROUP_COLUMNS,
        "scope",
        "horizon_step",
        "nominal_interval_level",
        "interval_available_count",
        "interval_evaluated_count",
        "empirical_coverage",
        "mean_interval_width_w",
    ]
    rows: list[dict[str, object]] = []
    grouping_variants = [
        ("overall", BASE_GROUP_COLUMNS),
        ("horizon_step", [*BASE_GROUP_COLUMNS, "horizon_step"]),
    ]

    for scope, group_columns in grouping_variants:
        for keys, group in forecasts.groupby(group_columns, sort=True, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)

            intervals_available = group["y_lower"].notna() & group["y_upper"].notna()

            if not intervals_available.any():
                continue

            evaluable = group.loc[intervals_available & group["target_eligible"]]

            if evaluable.empty:
                coverage = np.nan
                mean_width = np.nan
            else:
                covered = evaluable["y_true"].ge(evaluable["y_lower"]) & evaluable[
                    "y_true"
                ].le(evaluable["y_upper"])
                coverage = float(covered.mean())
                mean_width = float((evaluable["y_upper"] - evaluable["y_lower"]).mean())

            rows.append(
                {
                    **dict(zip(group_columns, keys, strict=True)),
                    "scope": scope,
                    "nominal_interval_level": nominal_interval_level,
                    "interval_available_count": int(intervals_available.sum()),
                    "interval_evaluated_count": len(evaluable),
                    "empirical_coverage": coverage,
                    "mean_interval_width_w": mean_width,
                }
            )

    result = pd.DataFrame(rows)

    if result.empty:
        return pd.DataFrame(columns=columns)

    if "horizon_step" not in result:
        result["horizon_step"] = pd.NA

    result = result.reindex(columns=columns)
    result["horizon_step"] = result["horizon_step"].astype("Int64")

    return result.sort_values(
        ["run_id", "split", "model_id", "scope", "horizon_step"], na_position="first"
    ).reset_index(drop=True)


def _calculate_target_exclusions(
    forecasts: pd.DataFrame,
    overall_metrics: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        *BASE_GROUP_COLUMNS,
        "target_exclusion_reason",
        "excluded_target_count",
        "excluded_target_share",
    ]
    excluded = forecasts.loc[~forecasts["target_eligible"]]

    if excluded.empty:
        return pd.DataFrame(columns=columns)

    exclusions = (
        excluded.groupby(
            [*BASE_GROUP_COLUMNS, "target_exclusion_reason"],
            as_index=False,
            dropna=False,
        )
        .size()
        .rename(columns={"size": "excluded_target_count"})
    )
    exclusions = exclusions.merge(
        overall_metrics[[*BASE_GROUP_COLUMNS, "possible_target_count"]],
        on=BASE_GROUP_COLUMNS,
        how="left",
        validate="many_to_one",
    )
    exclusions["excluded_target_share"] = (
        exclusions["excluded_target_count"] / exclusions["possible_target_count"]
    )

    return (
        exclusions[columns]
        .sort_values([*BASE_GROUP_COLUMNS, "target_exclusion_reason"])
        .reset_index(drop=True)
    )
