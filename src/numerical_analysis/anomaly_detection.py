from typing import cast

import numpy as np
import pandas as pd


def build_anomaly_detection(
    analysis_results: pd.DataFrame,
    *,
    min_reference_samples: int,
    min_residual_std_w: float,
    unusual_threshold: float,
    strong_anomaly_threshold: float,
    sample_period_hours: float,
    local_timezone: str,
) -> pd.DataFrame:
    result = analysis_results.copy()

    reference_columns = {
        "short_term": "short_term_mean",
        "daily": "daily_expected",
        "weekly": "weekly_expected",
        "long_term": "long_term_mean",
    }

    train_mask = result["split"] == "train"
    day_key = cast(pd.DatetimeIndex, result.index).tz_convert(local_timezone).normalize()

    for scale, reference_column in reference_columns.items():
        residual_column = f"{scale}_residual"
        score_column = f"{scale}_score"
        elevated_hours_column = f"{scale}_elevated_hours"

        result[residual_column] = result["current_power"] - result[reference_column]

        train_residuals = result.loc[
            train_mask,
            residual_column,
        ].dropna()

        if len(train_residuals) < min_reference_samples:
            result[score_column] = np.nan
            result[elevated_hours_column] = np.nan
            continue

        residual_mean = train_residuals.mean()
        residual_std = train_residuals.std()

        if pd.isna(residual_std) or residual_std < min_residual_std_w:
            result[score_column] = np.nan
            result[elevated_hours_column] = np.nan
            continue

        result[score_column] = (result[residual_column] - residual_mean) / residual_std

        elevated = result[score_column].abs() >= unusual_threshold
        
        # Anzahl auffälliger Stunden seit Mitternacht bis zur jeweiligen Zeile 
        result[elevated_hours_column] = (elevated.groupby(day_key).cumsum() * sample_period_hours).where(result[score_column].notna())
        

    score_columns = [
        "short_term_score",
        "daily_score",
        "weekly_score",
        "long_term_score",
    ]

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
    peak_abs: dict[str, float] = {}
    peak_signed: dict[str, float] = {}
    peak_timestamp_by_scale: dict[str, pd.Timestamp] = {}

    for scale in scales:
        score_column = f"{scale}_score"
        elevated_hours_column = f"{scale}_elevated_hours"
        scores = window[score_column]

        if scores.notna().any():
            abs_scores = scores.abs()
            peak_index = cast(pd.Timestamp, abs_scores.idxmax())
            peak_abs[scale] = abs_scores.loc[peak_index]
            peak_signed[scale] = scores.loc[peak_index]
            peak_timestamp_by_scale[scale] = peak_index
            summary[score_column] = peak_signed[scale]
            summary[elevated_hours_column] = (abs_scores >= unusual_threshold).sum() * sample_period_hours
        else:
            summary[score_column] = np.nan
            summary[elevated_hours_column] = np.nan

    if not peak_abs:
        summary["anomaly_score"] = np.nan
        summary["dominant_scale"] = pd.NA
        summary["anomaly_direction"] = pd.NA
        summary["anomaly_level"] = pd.NA
        summary["anomaly_peak_timestamp"] = pd.NaT
        return summary

    dominant_scale = max(peak_abs, key=lambda scale: peak_abs[scale])
    anomaly_score = peak_abs[dominant_scale]
    dominant_signed_score = peak_signed[dominant_scale]

    summary["anomaly_score"] = anomaly_score
    summary["dominant_scale"] = dominant_scale
    summary["anomaly_peak_timestamp"] = peak_timestamp_by_scale[dominant_scale]

    if dominant_signed_score > 0:
        summary["anomaly_direction"] = "high"
    elif dominant_signed_score < 0:
        summary["anomaly_direction"] = "low"
    else:
        summary["anomaly_direction"] = pd.NA

    if anomaly_score >= strong_anomaly_threshold:
        summary["anomaly_level"] = "strong_anomaly"
    elif anomaly_score >= unusual_threshold:
        summary["anomaly_level"] = "unusual"
    else:
        summary["anomaly_level"] = "normal"

    return summary