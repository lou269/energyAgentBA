import numpy as np
import pandas as pd


def build_anomaly_detection(
    analysis_results,
    *,
    min_reference_samples,
    unusual_threshold,
    strong_anomaly_threshold,
):
    """Berechnet standardisierte Anomaly Scores für alle Zeitskalen."""

    result = analysis_results.copy()

    reference_columns = {
        "short_term": "short_term_mean",
        "daily": "daily_expected",
        "weekly": "weekly_expected",
        "long_term": "long_term_mean",
    }

    train_mask = result["split"] == "train"

    for scale, reference_column in reference_columns.items():
        residual_column = f"{scale}_residual"
        score_column = f"{scale}_score"

        result[residual_column] = result["current_power"] - result[reference_column]

        train_residuals = result.loc[
            train_mask,
            residual_column,
        ].dropna()

        if len(train_residuals) < min_reference_samples:
            result[score_column] = np.nan
            continue

        residual_mean = train_residuals.mean()
        residual_std = train_residuals.std()

        if residual_std == 0 or pd.isna(residual_std):
            result[score_column] = np.nan
            continue

        result[score_column] = (
            result[residual_column] - residual_mean
        ) / residual_std

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