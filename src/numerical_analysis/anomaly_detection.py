from collections.abc import Mapping

import numpy as np
import pandas as pd

from src.common.timestamps import local_day_index


def resolve_dominant_scale(
    scale_scores: Mapping[str, float],
    *,
    direction_overrides: Mapping[str, float] | None = None,
) -> tuple[str, float, str | None]:
    dominant_scale = max(scale_scores, key=lambda scale: abs(scale_scores[scale]))
    signed_score = scale_scores[dominant_scale]

    override = (direction_overrides or {}).get(dominant_scale)
    direction_source = override if override is not None else signed_score
    direction = "high" if direction_source > 0 else "low" if direction_source < 0 else None

    return dominant_scale, abs(signed_score), direction


DEFAULT_REFERENCE_COLUMNS = {
    "short_term": ("current_power", "trend_reference_mean"),
    "daily": ("current_power", "daily_expected"),
    "weekly": ("current_power", "weekly_expected"),
    "long_term": ("current_power", "long_term_mean"),
}


def build_anomaly_detection(
    analysis_results: pd.DataFrame,
    *,
    min_reference_samples: int | Mapping[str, int],
    min_residual_std_w: float,
    unusual_threshold: float,
    strong_anomaly_threshold: float,
    sample_period_hours: float,
    local_timezone: str,
    reference_columns: Mapping[str, tuple[str, str]] | None = None,
    direction_override_columns: Mapping[str, tuple[str, str]] | None = None,
) -> pd.DataFrame:
    result = analysis_results.copy()

    reference_columns = reference_columns or DEFAULT_REFERENCE_COLUMNS
    direction_override_columns = direction_override_columns or {}

    train_mask = result["split"] == "train"
    day_key = local_day_index(result.index, local_timezone)

    for scale, (observed_column, expected_column) in reference_columns.items():
        residual_column = f"{scale}_residual"
        score_column = f"{scale}_score"
        elevated_hours_column = f"{scale}_elevated_hours"
        streak_days_column = f"{scale}_anomaly_streak_days"

        result[residual_column] = result[observed_column] - result[expected_column]

        train_residuals = result.loc[
            train_mask,
            residual_column,
        ].dropna()

        scale_min_reference_samples = (
            min_reference_samples[scale] if isinstance(min_reference_samples, Mapping) else min_reference_samples
        )

        if len(train_residuals) < scale_min_reference_samples:
            result[score_column] = np.nan
            result[elevated_hours_column] = np.nan
            result[streak_days_column] = np.nan
            continue

        residual_mean = train_residuals.mean()
        residual_std = train_residuals.std()

        if pd.isna(residual_std) or residual_std < min_residual_std_w:
            result[score_column] = np.nan
            result[elevated_hours_column] = np.nan
            result[streak_days_column] = np.nan
            continue

        result[score_column] = (result[residual_column] - residual_mean) / residual_std

        elevated = result[score_column].abs() >= unusual_threshold

        # Anzahl auffälliger Stunden seit Mitternacht bis zur jeweiligen Zeile
        result[elevated_hours_column] = (elevated.groupby(day_key).cumsum() * sample_period_hours).where(result[score_column].notna())

        # Tage am Stück, an denen diese Skala ununterbrochen auffällig war (für Tagesgranularität - eine
        # Unterbrechung durch einen unauffälligen Tag setzt den Zähler zurück auf 0)
        result[streak_days_column] = elevated.groupby((~elevated).cumsum()).cumsum().where(result[score_column].notna())

    score_columns = [f"{scale}_score" for scale in reference_columns]

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

    for scale in reference_columns:
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