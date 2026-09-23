import math
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


def anomaly_streak_days(
    score: pd.Series,
    *,
    threshold: float,
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
) -> pd.Series:
    elevated = (score.abs() >= threshold).where(score.notna())

    streak_min_periods = math.ceil(streak_tolerance_window_days * rolling_window_min_coverage)
    streak_raw = elevated.rolling(window=streak_tolerance_window_days, min_periods=streak_min_periods).sum()

    return streak_raw.fillna(0).where(elevated.notna(), np.nan)


def build_anomaly_detection(
    analysis_results: pd.DataFrame,
    *,
    reference_columns: Mapping[str, tuple[str, str]],
    direction_override_columns: Mapping[str, tuple[str, str]],
    min_reference_samples: Mapping[str, int],
    min_residual_std_w: float,
    unusual_threshold: float,
    strong_anomaly_threshold: float,
    gate_scales: Sequence[str],
    streak_thresholds: Mapping[str, float],
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
) -> pd.DataFrame:
    result = analysis_results.copy()

    train_mask = result["split"] == "train"

    for scale, (observed_column, expected_column) in reference_columns.items():
        residual_column = f"{scale}_residual"
        score_column = f"{scale}_score"
        streak_days_column = f"{scale}_anomaly_streak_days"
        sustained_column = f"{scale}_sustained"

        result[residual_column] = result[observed_column] - result[expected_column]

        train_residuals = result.loc[
            train_mask,
            residual_column,
        ].dropna()

        residual_mean = train_residuals.mean()
        residual_std = train_residuals.std()

        # zu wenig Referenz oder fast keine Streuung -> lieber kein Score als ein riesiger, unzuverlässiger
        if len(train_residuals) < min_reference_samples[scale] or pd.isna(residual_std) or residual_std < min_residual_std_w:
            result[score_column] = np.nan
            result[streak_days_column] = np.nan
            result[sustained_column] = False
            continue

        result[score_column] = (result[residual_column] - residual_mean) / residual_std

        result[streak_days_column] = anomaly_streak_days(
            result[score_column],
            threshold=streak_thresholds.get(scale, unusual_threshold),
            streak_tolerance_window_days=streak_tolerance_window_days,
            rolling_window_min_coverage=rolling_window_min_coverage,
        )

        result[sustained_column] = result[streak_days_column] >= sustained_anomaly_streak_days

    # öffnet das Gate auch an einem sonst unauffälligen Tag und ist zugleich die new_pattern-Bedingung der Regel
    sustained_columns = [f"{scale}_sustained" for scale in reference_columns]
    result["sustained_drift"] = result[sustained_columns].sum(axis=1) >= min_sustained_scales

    score_columns = [f"{scale}_score" for scale in gate_scales]

    absolute_scores = result[score_columns].abs()

    result["anomaly_score"] = absolute_scores.max(axis=1, skipna=True)

    result["dominant_scale"] = pd.NA

    valid_scores = absolute_scores.notna().any(axis=1)

    result.loc[valid_scores, "dominant_scale"] = (
        absolute_scores.loc[valid_scores]
        .idxmax(axis=1)
        .astype(str)
        .str.replace("_score", "", regex=False)
    )

    direction_values = pd.Series(np.nan, index=result.index)

    for scale in gate_scales:
        mask = result["dominant_scale"] == scale

        if scale in direction_override_columns:
            observed_column, expected_column = direction_override_columns[scale]
            direction_values.loc[mask] = result.loc[mask, observed_column] - result.loc[mask, expected_column]
        else:
            direction_values.loc[mask] = result.loc[mask, f"{scale}_score"]

    result["anomaly_direction"] = pd.NA
    result.loc[direction_values > 0, "anomaly_direction"] = "high"
    result.loc[direction_values < 0, "anomaly_direction"] = "low"

    result["anomaly_level"] = "normal"
    result.loc[
        result["anomaly_score"] >= unusual_threshold,
        "anomaly_level",
    ] = "unusual"
    result.loc[
        result["anomaly_score"] >= strong_anomaly_threshold,
        "anomaly_level",
    ] = "strong_anomaly"
    result.loc[result["anomaly_score"].isna(), "anomaly_level"] = pd.NA

    result.index.name = "timestamp"

    return result