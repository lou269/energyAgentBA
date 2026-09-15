from collections.abc import Mapping
from typing import cast

import numpy as np
import pandas as pd


def resolve_dominant_scale(scale_scores: Mapping[str, float]) -> tuple[str, float, str | None]:
    dominant_scale = max(scale_scores, key=lambda scale: abs(scale_scores[scale]))
    signed_score = scale_scores[dominant_scale]
    direction = "high" if signed_score > 0 else "low" if signed_score < 0 else None

    return dominant_scale, abs(signed_score), direction


DEFAULT_REFERENCE_COLUMNS = {
    "short_term": "short_term_mean",
    "daily": "daily_expected",
    "weekly": "weekly_expected",
    "long_term": "long_term_mean",
}


def build_anomaly_detection(
    analysis_results: pd.DataFrame,
    *,
    min_reference_samples: int,
    min_residual_std_w: float,
    unusual_threshold: float,
    strong_anomaly_threshold: float,
    sample_period_hours: float,
    local_timezone: str,
    reference_columns: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    result = analysis_results.copy()

    reference_columns = reference_columns or DEFAULT_REFERENCE_COLUMNS

    train_mask = result["split"] == "train"
    day_key = cast(pd.DatetimeIndex, result.index).tz_convert(local_timezone).normalize()

    for scale, reference_column in reference_columns.items():
        residual_column = f"{scale}_residual"
        score_column = f"{scale}_score"
        elevated_hours_column = f"{scale}_elevated_hours"
        streak_days_column = f"{scale}_anomaly_streak_days"

        result[residual_column] = result["current_power"] - result[reference_column]

        train_residuals = result.loc[
            train_mask,
            residual_column,
        ].dropna()

        if len(train_residuals) < min_reference_samples:
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

    dominant_scores = pd.Series(np.nan, index=result.index)

    for scale in reference_columns:
        mask = result["dominant_scale"] == scale
        dominant_scores.loc[mask] = result.loc[mask, f"{scale}_score"]

    result["anomaly_direction"] = pd.NA
    result.loc[dominant_scores > 0, "anomaly_direction"] = "high"
    result.loc[dominant_scores < 0, "anomaly_direction"] = "low"

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


def aggregate_daily_anomaly(
    anomaly: pd.DataFrame,
    *,
    target_timestamp: pd.Timestamp,
    window_hours: float,
    sample_period_hours: float,
    unusual_threshold: float,
    strong_anomaly_threshold: float,
) -> dict[str, object]:
    # Ersetzt die Einzelstunden-Sicht auf target_timestamp durch eine Zusammenfassung der letzten
    # window_hours Stunden davor - eine Stunde allein ist kein verlässlicher Indikator für den Tag als Ganzes
    scales = ("short_term", "daily", "weekly", "long_term")
    n_samples = max(1, round(window_hours / sample_period_hours))
    window = anomaly.loc[:target_timestamp].tail(n_samples)

    summary: dict[str, object] = {}
    peak_signed: dict[str, float] = {}
    peak_timestamp_by_scale: dict[str, pd.Timestamp] = {}

    for scale in scales:
        score_column = f"{scale}_score"
        elevated_hours_column = f"{scale}_elevated_hours"
        scores = window[score_column]

        if scores.notna().any():
            abs_scores = scores.abs()
            peak_index = cast(pd.Timestamp, abs_scores.idxmax())
            peak_signed[scale] = scores.loc[peak_index]
            peak_timestamp_by_scale[scale] = peak_index
            summary[score_column] = peak_signed[scale]
            summary[elevated_hours_column] = (abs_scores >= unusual_threshold).sum() * sample_period_hours
        else:
            summary[score_column] = np.nan
            summary[elevated_hours_column] = np.nan

    if not peak_signed:
        summary["anomaly_score"] = np.nan
        summary["dominant_scale"] = pd.NA
        summary["anomaly_direction"] = pd.NA
        summary["anomaly_level"] = pd.NA
        summary["anomaly_peak_timestamp"] = pd.NaT
        return summary

    dominant_scale, anomaly_score, direction = resolve_dominant_scale(peak_signed)

    summary["anomaly_score"] = anomaly_score
    summary["dominant_scale"] = dominant_scale
    summary["anomaly_peak_timestamp"] = peak_timestamp_by_scale[dominant_scale]
    summary["anomaly_direction"] = direction if direction is not None else pd.NA

    if anomaly_score >= strong_anomaly_threshold:
        summary["anomaly_level"] = "strong_anomaly"
    elif anomaly_score >= unusual_threshold:
        summary["anomaly_level"] = "unusual"
    else:
        summary["anomaly_level"] = "normal"

    return summary