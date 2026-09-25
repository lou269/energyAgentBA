import pandas as pd

from experiments.k3_detection.k3_calibration import apply_gate, select_operating_points


def _scores(daily: list[float], weekly: float, long_term: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "variant": "REF_ROLL60",
            "cutover_date": "2014-04-15",
            "kind": "control",
            "days_since_cutover": range(len(daily)),
            "daily_score": daily,
            "weekday_score": 0.5,
            "weekly_score": weekly,
            "long_term_score": long_term,
        }
    )


def _gate(results: pd.DataFrame, long_term_threshold: float) -> pd.DataFrame:
    return apply_gate(
        results,
        gate_threshold=2.5,
        slow_scale_thresholds={"weekly": 1.25, "long_term": long_term_threshold},
        gate_scales=("daily", "weekday"),
        streak_tolerance_window_days=7,
        rolling_window_min_coverage=0.8,
        sustained_anomaly_streak_days=6,
        min_sustained_scales=2,
    )


def test_slow_scales_use_their_own_streak_threshold() -> None:
    results = _scores([0.5] * 7 + [3.0, 0.5, 0.5], weekly=1.5, long_term=1.5)

    gated = _gate(results, long_term_threshold=1.0)

    # Tag 0 bis 5 fehlt die Streak-Vorgeschichte
    assert gated["days_since_cutover"].tolist() == [6, 7, 8, 9]
    assert gated["alarm"].tolist() == [False, True, False, False]
    # 1,5 liegt unter gate_threshold, reicht mit den eigenen Schwellen aber auf beiden langsamen Skalen
    assert gated["new_pattern"].all()

    # nur noch weekly dauerhaft erhöht, min_sustained_scales=2 wird nicht erreicht
    assert not _gate(results, long_term_threshold=2.0)["new_pattern"].any()


def test_operating_point_keeps_the_false_alarm_budget_before_detection() -> None:
    grid_metrics = pd.DataFrame(
        {
            "variant": "REF_ROLL60",
            "cutover_date": "2014-04-15",
            "gate_threshold": [2.0, 2.5, 2.5, 3.0],
            "weekly_threshold": [1.0, 1.0, 2.0, 1.0],
            "alarm_rate": [0.08, 0.04, 0.04, 0.02],
            "false_new_pattern": [0, 2, 1, 0],
            "first_event_new_pattern_day": [3.0, 3.0, float("nan"), 3.0],
        }
    )

    point = select_operating_points(
        grid_metrics,
        slow_scales=("weekly",),
        target_alarm_rate=0.05,
        max_false_new_pattern=1.0,
    ).iloc[0]

    # 2,0 reißt die Zielrate, 3,0 wäre unnötig streng
    assert point["gate_threshold"] == 2.5
    assert point["weekly_threshold"] == 2.0
    assert point["detected"] == 0
