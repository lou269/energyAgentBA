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
    # 1/-1 an auffälligen Tagen, 0 an unauffälligen, NaN ohne Wert
    direction = pd.Series(np.sign(score), index=score.index).where(
        score.abs() >= threshold, 0.0
    )
    direction = direction.where(score.notna())

    # ein auffälliger Tag in Gegenrichtung beginnt die Streak neu, ein unauffälliger nicht
    last_direction = direction.replace(0.0, np.nan).ffill()
    run_id = last_direction.ne(last_direction.shift()).cumsum()
    streak_raw = (
        direction.abs()
        .groupby(run_id)
        .rolling(window=streak_tolerance_window_days, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )

    streak_min_periods = math.ceil(
        streak_tolerance_window_days * rolling_window_min_coverage
    )
    enough_days = (
        score.notna().rolling(window=streak_tolerance_window_days, min_periods=1).sum()
        >= streak_min_periods
    )

    # zu wenige gültige Tage im Fenster bleiben NaN (unbekannt), nicht 0 auffällige Tage
    return streak_raw.where(enough_days & score.notna(), np.nan)


def build_level_shift_streaks(
    streak_values: pd.DataFrame,
    *,
    streak_thresholds: Mapping[str, float],
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
) -> pd.DataFrame:
    result = pd.DataFrame(index=streak_values.index)

    for scale in streak_values.columns:
        streak_days = anomaly_streak_days(
            streak_values[scale],
            threshold=streak_thresholds[scale],
            streak_tolerance_window_days=streak_tolerance_window_days,
            rolling_window_min_coverage=rolling_window_min_coverage,
        )
        result[f"{scale}_anomaly_streak_days"] = streak_days
        result[f"{scale}_sustained"] = streak_days >= sustained_anomaly_streak_days

    # öffnet das Gate auch an einem sonst unauffälligen Tag und ist die new_pattern-Bedingung der Regel
    sustained_columns = [f"{scale}_sustained" for scale in streak_values.columns]
    result["sustained_drift"] = (
        result[sustained_columns].sum(axis=1) >= min_sustained_scales
    )

    return result


def build_anomaly_detection(
    analysis_results: pd.DataFrame,
    *,
    reference_columns: Mapping[str, tuple[str, str, str]],
    direction_override_columns: Mapping[str, tuple[str, str]],
    min_reference_samples: Mapping[str, int],
    min_residual_std_w: float,
    unusual_thresholds: Mapping[str, float],
    single_day_scales: Sequence[str],
    robust_scales: Sequence[str],
) -> pd.DataFrame:
    result = analysis_results.copy()

    for scale, (
        observed_column,
        expected_column,
        reference_column,
    ) in reference_columns.items():
        residual_column = f"{scale}_residual"
        score_column = f"{scale}_score"

        result[residual_column] = result[observed_column] - result[expected_column]

        # Residuen der Referenztage, der bewertete Tag selbst ist nie dabei
        reference_residuals = (
            result[reference_column] - result[expected_column]
        ).dropna()

        if scale in robust_scales:
            residual_center = reference_residuals.median()
            # 1,4826: MAD = Standardabweichung bei normalverteilten Werten
            residual_spread = (
                1.4826 * (reference_residuals - residual_center).abs().median()
            )
        else:
            residual_center = reference_residuals.mean()
            residual_spread = reference_residuals.std()

        # zu wenig Referenz oder fast keine Streuung -> lieber kein Score als ein riesiger, unzuverlässiger
        if (
            len(reference_residuals) < min_reference_samples[scale]
            or pd.isna(residual_spread)
            or residual_spread < min_residual_std_w
        ):
            result[score_column] = np.nan
            continue

        result[score_column] = (
            result[residual_column] - residual_center
        ) / residual_spread

    score_columns = [f"{scale}_score" for scale in single_day_scales]

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

    for scale in single_day_scales:
        mask = result["dominant_scale"] == scale

        if scale in direction_override_columns:
            observed_column, expected_column = direction_override_columns[scale]
            direction_values.loc[mask] = (
                result.loc[mask, observed_column] - result.loc[mask, expected_column]
            )
        else:
            direction_values.loc[mask] = result.loc[mask, f"{scale}_score"]

    result["anomaly_direction"] = pd.NA
    result.loc[direction_values > 0, "anomaly_direction"] = "high"
    result.loc[direction_values < 0, "anomaly_direction"] = "low"

    # jede Gate-Skala gegen ihre eigene Schwelle
    unusual = pd.concat(
        [
            result[f"{scale}_score"].abs() >= unusual_thresholds[scale]
            for scale in single_day_scales
        ],
        axis=1,
    ).any(axis=1)

    result["anomaly_level"] = "normal"
    result.loc[unusual, "anomaly_level"] = "unusual"
    result.loc[result["anomaly_score"].isna(), "anomaly_level"] = pd.NA

    result.index.name = "timestamp"

    return result
