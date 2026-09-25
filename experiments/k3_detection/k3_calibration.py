from collections.abc import Mapping, Sequence
from itertools import product

import pandas as pd

from experiments.common.evaluation import (
    add_days_since_cutover,
    pair_with_control,
    summarize_event_response,
)
from experiments.k3_detection.k3_config import K3Config
from experiments.k3_detection.k3_evaluation import PAIR_KEYS
from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.anomaly_detection import anomaly_streak_days


SERIES_KEYS = ["variant", "cutover_date", "kind"]
WINDOW_KEYS = ["variant", "cutover_date"]


def threshold_columns(slow_scales: Sequence[str]) -> list[str]:
    return ["gate_threshold"] + [f"{scale}_threshold" for scale in slow_scales]


def apply_gate(
    results: pd.DataFrame,
    *,
    gate_threshold: float,
    slow_scale_thresholds: Mapping[str, float],
    gate_scales: Sequence[str],
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
) -> pd.DataFrame:
    gated = results.sort_values(SERIES_KEYS + ["days_since_cutover"]).reset_index(
        drop=True
    )
    series_position = gated.groupby(SERIES_KEYS).cumcount()

    gate_score_columns = [f"{scale}_score" for scale in gate_scales]
    gated["anomaly_score"] = gated[gate_score_columns].abs().max(axis=1)
    gated["alarm"] = gated["anomaly_score"] >= gate_threshold

    streak_thresholds = {scale: gate_threshold for scale in gate_scales}
    streak_thresholds.update(slow_scale_thresholds)

    sustained_scales = pd.Series(0, index=gated.index)

    for scale, threshold in streak_thresholds.items():
        streak = gated.groupby(SERIES_KEYS)[f"{scale}_score"].transform(
            lambda score: anomaly_streak_days(
                score,
                threshold=threshold,
                streak_tolerance_window_days=streak_tolerance_window_days,
                rolling_window_min_coverage=rolling_window_min_coverage,
            )
        )

        sustained_scales += streak >= sustained_anomaly_streak_days

    # entspricht sustained_drift aus build_anomaly_detection, isolated gibt es keinen Reset, der die Drift wieder schließt
    gated["new_pattern"] = sustained_scales >= min_sustained_scales

    # die ersten Tage haben offline keine Vorgeschichte für den Streak -> nicht mitwerten
    return gated.loc[series_position >= streak_tolerance_window_days - 1]


def summarize_operating_point(gated: pd.DataFrame) -> pd.DataFrame:
    control = gated.loc[gated["kind"] == "control"]

    # isolated bleibt eine Drift oft wochenlang stehen, deshalb zählt nur der erste Tag
    previous_new_pattern = control.groupby(WINDOW_KEYS)["new_pattern"].shift(
        fill_value=False
    )
    control = control.assign(
        new_pattern_onset=control["new_pattern"] & ~previous_new_pattern
    )

    summary = control.groupby(WINDOW_KEYS, as_index=False).agg(
        alarm_rate=("alarm", "mean"),
        false_new_pattern=("new_pattern_onset", "sum"),
    )

    # isolated läuft nur step als Ereignis, eine Zeile je Fenster
    response = summarize_event_response(
        pair_with_control(gated, PAIR_KEYS), ["mode", "kind"] + WINDOW_KEYS
    )

    return summary.merge(
        response[WINDOW_KEYS + ["first_event_new_pattern_day"]], on=WINDOW_KEYS
    )


def build_grid_metrics(
    results: pd.DataFrame,
    *,
    gate_thresholds: Sequence[float],
    slow_scale_thresholds: Sequence[float],
    gate_scales: Sequence[str],
    slow_scales: Sequence[str],
    streak_tolerance_window_days: int,
    rolling_window_min_coverage: float,
    sustained_anomaly_streak_days: int,
    min_sustained_scales: int,
) -> pd.DataFrame:
    isolated = results.loc[results["mode"].eq("isolated")]
    grid_rows: list[pd.DataFrame] = []

    for gate_threshold in gate_thresholds:
        for slow_combination in product(slow_scale_thresholds, repeat=len(slow_scales)):
            thresholds = dict(zip(slow_scales, slow_combination))

            gated = apply_gate(
                isolated,
                gate_threshold=gate_threshold,
                slow_scale_thresholds=thresholds,
                gate_scales=gate_scales,
                streak_tolerance_window_days=streak_tolerance_window_days,
                rolling_window_min_coverage=rolling_window_min_coverage,
                sustained_anomaly_streak_days=sustained_anomaly_streak_days,
                min_sustained_scales=min_sustained_scales,
            )

            point = summarize_operating_point(gated)
            point["gate_threshold"] = gate_threshold
            for scale, threshold in thresholds.items():
                point[f"{scale}_threshold"] = threshold

            grid_rows.append(point)

    return pd.concat(grid_rows, ignore_index=True)


def select_operating_points(
    grid_metrics: pd.DataFrame,
    *,
    slow_scales: Sequence[str],
    target_alarm_rate: float,
    max_false_new_pattern: float,
) -> pd.DataFrame:
    columns = threshold_columns(slow_scales)

    points = grid_metrics.groupby(["variant"] + columns, as_index=False).agg(
        alarm_rate=("alarm_rate", "mean"),
        false_new_pattern=("false_new_pattern", "mean"),
        detected=("first_event_new_pattern_day", "count"),
        detection_day=("first_event_new_pattern_day", "mean"),
    )

    # Einzeltage: die niedrigste Schwelle, die im Mittel noch unter target_alarm_rate bleibt
    points["target_excess"] = (points["alarm_rate"] - target_alarm_rate).clip(lower=0)
    gate_choice = points.sort_values(
        ["target_excess", "gate_threshold"]
    ).drop_duplicates("variant")
    points = points.merge(
        gate_choice[["variant", "gate_threshold"]], on=["variant", "gate_threshold"]
    )

    # Drift: zuerst das Fehlalarm-Budget einhalten, danach möglichst oft und früh erkennen
    points["budget_excess"] = (
        points["false_new_pattern"] - max_false_new_pattern
    ).clip(lower=0)
    points = points.sort_values(
        [
            "target_excess",
            "budget_excess",
            "detected",
            "detection_day",
            "false_new_pattern",
        ],
        ascending=[True, True, False, True, True],
    )

    # pro Variante bleibt der beste Punkt, die erste Zeile ist damit auch die beste Variante
    points = (
        points.drop_duplicates("variant")
        .drop(columns=["target_excess", "budget_excess"])
        .reset_index(drop=True)
    )
    points["rank"] = points.index + 1

    return points


def operating_points_by_cutover(
    operating_points: pd.DataFrame,
    grid_metrics: pd.DataFrame,
    *,
    slow_scales: Sequence[str],
) -> pd.DataFrame:
    thresholds = threshold_columns(slow_scales)
    selected = operating_points[["variant", "rank"] + thresholds]

    return selected.merge(grid_metrics, on=["variant"] + thresholds).sort_values(
        ["rank", "cutover_date"]
    )


def leave_one_cutover_out(
    grid_metrics: pd.DataFrame,
    *,
    slow_scales: Sequence[str],
    target_alarm_rate: float,
    max_false_new_pattern: float,
) -> pd.DataFrame:
    cutover_dates = sorted(grid_metrics["cutover_date"].unique())
    folds: list[pd.DataFrame] = []

    for held_out in cutover_dates:
        operating_points = select_operating_points(
            grid_metrics.loc[grid_metrics["cutover_date"] != held_out],
            slow_scales=slow_scales,
            target_alarm_rate=target_alarm_rate,
            max_false_new_pattern=max_false_new_pattern,
        )

        held_out_metrics = grid_metrics.loc[grid_metrics["cutover_date"] == held_out]

        folds.append(
            operating_points.merge(
                held_out_metrics,
                on=["variant"] + threshold_columns(slow_scales),
                suffixes=("_calibration", "_held_out"),
            )
        )

    return pd.concat(folds, ignore_index=True)


def calibrate(
    results: pd.DataFrame,
    k3_config: K3Config,
    numerical_analysis_config: NumericalAnalysisConfig,
) -> dict[str, pd.DataFrame]:
    # Schwellen je Referenzfenster bei gleicher Fehlalarmrate, rein offline auf den isolated-Läufen
    slow_scales = k3_config.slow_scales

    grid_metrics = build_grid_metrics(
        add_days_since_cutover(results),
        gate_thresholds=k3_config.gate_thresholds,
        slow_scale_thresholds=k3_config.slow_scale_thresholds,
        gate_scales=numerical_analysis_config.gate_scales,
        slow_scales=slow_scales,
        streak_tolerance_window_days=numerical_analysis_config.streak_tolerance_window_days,
        rolling_window_min_coverage=numerical_analysis_config.rolling_window_min_coverage,
        sustained_anomaly_streak_days=numerical_analysis_config.sustained_anomaly_streak_days,
        min_sustained_scales=numerical_analysis_config.min_sustained_scales,
    )
    operating_points = select_operating_points(
        grid_metrics,
        slow_scales=slow_scales,
        target_alarm_rate=k3_config.target_alarm_rate,
        max_false_new_pattern=k3_config.max_false_new_pattern,
    )

    return {
        "grid": grid_metrics,
        "operating_points": operating_points,
        "by_cutover": operating_points_by_cutover(
            operating_points, grid_metrics, slow_scales=slow_scales
        ),
        "loco": leave_one_cutover_out(
            grid_metrics,
            slow_scales=slow_scales,
            target_alarm_rate=k3_config.target_alarm_rate,
            max_false_new_pattern=k3_config.max_false_new_pattern,
        ),
    }
