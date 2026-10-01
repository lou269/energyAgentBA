from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import product
from typing import cast

import pandas as pd

from experiments.common.evaluation import (
    FIRST_ANALYZED_DAY,
    add_days_since_cutover,
    pair_with_control,
)
from experiments.k2_detection.k2_config import STREAK_THRESHOLD_COLUMNS
from experiments.k2_detection.k2_evaluation import (
    PAIR_KEYS,
    CalibrationSummary,
    near_control_new_pattern,
)
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.anomaly_detection import build_level_shift_streaks
from src.numerical_analysis.daily_analysis import LEVEL_SHIFT_VALUE_COLUMNS


SERIES_KEYS = ["variant", "cutover_date", "kind"]
WINDOW_KEYS = ["variant", "cutover_date"]


def build_gate_threshold(
    results: pd.DataFrame, *, single_day_scales: Sequence[str], target_alarm_pct: float
) -> pd.DataFrame:
    # eine Schwelle für alle Einzeltag-Skalen: der größte Score des Tages wird nur an so vielen Kontrolltagen überschritten, wie gewollt
    control = results.loc[results["kind"].eq("control")]
    scores = control[[f"{scale}_score" for scale in single_day_scales]].abs()
    strongest = scores.max(axis=1).where(scores.notna().any(axis=1))
    threshold = strongest.quantile(1 - target_alarm_pct / 100)

    days = pd.DataFrame(
        {
            "cutover_date": control["cutover_date"],
            "alarm": strongest.ge(threshold).where(strongest.notna()),
        }
    )

    return (
        days.groupby("cutover_date", as_index=False)
        .agg(alarm_rate=("alarm", "mean"))
        .assign(gate_threshold=threshold)
    )


def apply_streaks(
    results: pd.DataFrame,
    *,
    streak_thresholds: Mapping[str, float],
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
) -> pd.DataFrame:
    # je Reihe dieselbe Rechnung wie im Zyklus, auf den Werten, die jeder Tag an seinem Entscheidungstag hatte
    ordered = results.sort_values(SERIES_KEYS + ["days_since_cutover"])
    sustained_drift = ordered.groupby(SERIES_KEYS, group_keys=False)[
        list(LEVEL_SHIFT_VALUE_COLUMNS.values())
    ].apply(
        lambda values: build_level_shift_streaks(
            values.rename(
                columns={
                    column: scale for scale, column in LEVEL_SHIFT_VALUE_COLUMNS.items()
                }
            ),
            streak_thresholds=streak_thresholds,
            sustained_anomaly_streak_days=sustained_anomaly_streak_days,
            min_sustained_scales=min_sustained_scales,
            streak_tolerance_window_days=streak_tolerance_window_days,
            rolling_window_min_coverage=rolling_window_min_coverage,
        )["sustained_drift"]
    )

    # entspricht new_pattern der Regel, isolated gibt es keinen Reset, der die Drift wieder schließt
    return ordered.assign(new_pattern=cast(pd.Series, sustained_drift))


def summarize_streak_point(
    gated: pd.DataFrame, control_reset_tolerance_days: int
) -> pd.DataFrame:
    # isolated bleibt eine Drift oft wochenlang stehen, im Kreislauf setzt schon ihr erster Tag zurück, deshalb zählt nur der
    previous_new_pattern = gated.groupby(SERIES_KEYS)["new_pattern"].shift(
        fill_value=False
    )
    onsets = gated.assign(new_pattern=gated["new_pattern"] & ~previous_new_pattern)

    summary = (
        onsets.loc[onsets["kind"].eq("control")]
        .groupby(WINDOW_KEYS, as_index=False)
        .agg(false_new_pattern=("new_pattern", "sum"))
    )

    # erkannt wie im Kreislauf: erster eigener Beginn ab Cutover, die Kontrolle hat keinen
    # isolated läuft nur step als Ereignis, eine Zeile je Fenster
    paired = pair_with_control(onsets, PAIR_KEYS)
    own = paired["event_new_pattern"] & ~near_control_new_pattern(
        paired, control_reset_tolerance_days
    )
    detected = (
        paired.loc[own & paired["days_since_cutover"].ge(FIRST_ANALYZED_DAY)]
        .groupby(WINDOW_KEYS, as_index=False)
        .agg(first_event_new_pattern_day=("days_since_cutover", "min"))
    )

    return summary.merge(detected, on=WINDOW_KEYS, how="left")


def build_streak_grid(
    results: pd.DataFrame,
    *,
    threshold_values: Mapping[str, Sequence[float]],
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
    control_reset_tolerance_days: int,
) -> pd.DataFrame:
    grid_rows: list[pd.DataFrame] = []

    for combination in product(*threshold_values.values()):
        thresholds = dict(zip(threshold_values, combination))

        gated = apply_streaks(
            results,
            streak_thresholds=thresholds,
            streak_tolerance_window_days=streak_tolerance_window_days,
            rolling_window_min_coverage=rolling_window_min_coverage,
            sustained_anomaly_streak_days=sustained_anomaly_streak_days,
            min_sustained_scales=min_sustained_scales,
        )

        point = summarize_streak_point(gated, control_reset_tolerance_days)
        for scale, threshold in thresholds.items():
            point[STREAK_THRESHOLD_COLUMNS[scale]] = threshold

        grid_rows.append(point)

    return pd.concat(grid_rows, ignore_index=True)


def apply_calibration(
    numerical_analysis_config: NumericalAnalysisConfig,
    summary: CalibrationSummary,
    gate_threshold_decimals: int,
) -> NumericalAnalysisConfig:
    selected = summary.streak_selected

    return replace(
        numerical_analysis_config,
        unusual_threshold=round(summary.gate_threshold, gate_threshold_decimals),
        weekday_streak_threshold=selected["weekday"],
        weekly_streak_threshold=selected["weekly"],
        long_term_streak_threshold_pct=selected["long_term"],
    )


def calibrate(
    results: pd.DataFrame,
    *,
    single_day_scales: Sequence[str],
    target_alarm_pct: float,
    threshold_values: Mapping[str, Sequence[float]],
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
    control_reset_tolerance_days: int,
) -> dict[str, pd.DataFrame]:
    isolated = add_days_since_cutover(results.loc[results["mode"].eq("isolated")])

    return {
        "gate_threshold": build_gate_threshold(
            isolated,
            single_day_scales=single_day_scales,
            target_alarm_pct=target_alarm_pct,
        ),
        "streak_sensitivity": build_streak_grid(
            isolated,
            threshold_values=threshold_values,
            streak_tolerance_window_days=streak_tolerance_window_days,
            rolling_window_min_coverage=rolling_window_min_coverage,
            sustained_anomaly_streak_days=sustained_anomaly_streak_days,
            min_sustained_scales=min_sustained_scales,
            control_reset_tolerance_days=control_reset_tolerance_days,
        ),
    }
