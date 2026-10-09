# python -m pytest tests/unit/numerical_analysis/test_anomaly_detection.py -v

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from src.numerical_analysis.anomaly_detection import (
    anomaly_streak_days,
    build_anomaly_detection,
    build_level_shift_streaks,
)


REFERENCE_RESIDUALS = [-2.0, -1.0, 0.0, 1.0, 2.0] * 10
EXPECTED = 100.0

REFERENCE_COLUMNS = {
    "daily": ("daily_obs", "daily_exp", "daily_ref"),
    "weekday": ("weekday_obs", "weekday_exp", "weekday_ref"),
}


def _frame(reference: Sequence[float], analyzed: dict[str, float]) -> pd.DataFrame:
    # die letzte Zeile ist der eingeordnete Tag, sie steht selbst nicht in der Referenz
    n = len(reference)
    index = pd.date_range("2024-01-01", periods=n + 1, freq="D", tz="UTC")
    columns = {}
    for scale, residual in analyzed.items():
        columns[f"{scale}_exp"] = EXPECTED
        columns[f"{scale}_ref"] = [EXPECTED + r for r in reference] + [np.nan]
        columns[f"{scale}_obs"] = [EXPECTED + r for r in reference] + [
            EXPECTED + residual
        ]

    return pd.DataFrame(columns, index=index)


def _detect(
    frame: pd.DataFrame,
    *,
    robust_scales: Sequence[str] = (),
    min_reference_samples: int = 5,
    min_residual_std_w: float = 0.1,
    thresholds: dict[str, float] | None = None,
    direction_override: dict[str, tuple[str, str]] | None = None,
) -> pd.Series:
    scales = [s for s in REFERENCE_COLUMNS if f"{s}_obs" in frame]

    return build_anomaly_detection(
        frame,
        reference_columns={s: REFERENCE_COLUMNS[s] for s in scales},
        direction_override_columns=direction_override or {},
        min_reference_samples={s: min_reference_samples for s in scales},
        min_residual_std_w=min_residual_std_w,
        unusual_thresholds=thresholds or {s: 2.0 for s in scales},
        single_day_scales=scales,
        robust_scales=robust_scales,
    ).iloc[-1]


def test_robust_score_uses_median_mad() -> None:
    reference = np.array(REFERENCE_RESIDUALS + [100.0])
    frame = _frame(reference.tolist(), {"daily": 6.0})

    robust = _detect(frame, robust_scales=("daily",))["daily_score"]
    classic = _detect(frame)["daily_score"]

    center = np.median(reference)
    mad = 1.4826 * np.median(np.abs(reference - center))
    assert robust == pytest.approx((6.0 - center) / mad)
    assert classic == pytest.approx((6.0 - reference.mean()) / reference.std(ddof=1))
    assert robust > classic


def test_analyzed_day_not_in_own_reference() -> None:
    small = _detect(_frame(REFERENCE_RESIDUALS, {"daily": 4.0}))["daily_score"]
    large = _detect(_frame(REFERENCE_RESIDUALS, {"daily": 400.0}))["daily_score"]

    # ein riesiger Ausreißer am eingeordneten Tag verschiebt die Streuung der Referenz nicht
    assert large == pytest.approx(small * 100)


def test_no_score_without_reference() -> None:
    few = _detect(_frame(REFERENCE_RESIDUALS[:4], {"daily": 5.0}))
    flat = _detect(_frame([0.001, -0.001] * 20, {"daily": 5.0}), min_residual_std_w=1.0)

    assert np.isnan(few["daily_score"])
    assert np.isnan(flat["daily_score"])
    assert pd.isna(few["anomaly_level"])


def test_dominant_scale_gives_direction() -> None:
    spread = pd.Series(REFERENCE_RESIDUALS).std()
    frame = _frame(
        REFERENCE_RESIDUALS, {"daily": 1.0 * spread, "weekday": -3.0 * spread}
    )

    row = _detect(frame, thresholds={"daily": 2.0, "weekday": 2.5})

    assert row["dominant_scale"] == "weekday"
    assert row["anomaly_score"] == pytest.approx(3.0)
    assert row["anomaly_direction"] == "low"
    assert row["anomaly_level"] == "unusual"


def test_own_threshold_per_scale() -> None:
    spread = pd.Series(REFERENCE_RESIDUALS).std()
    frame = _frame(
        REFERENCE_RESIDUALS, {"daily": 2.5 * spread, "weekday": 2.5 * spread}
    )

    quiet = _detect(frame, thresholds={"daily": 3.0, "weekday": 3.0})
    alarm = _detect(frame, thresholds={"daily": 3.0, "weekday": 2.0})

    assert quiet["anomaly_level"] == "normal"
    assert alarm["anomaly_level"] == "unusual"


def test_direction_override() -> None:
    spread = pd.Series(REFERENCE_RESIDUALS).std()
    frame = _frame(REFERENCE_RESIDUALS, {"daily": 3.0 * spread})
    # daily misst die Streuung im Tag, die Richtung kommt vom Tagesmittel
    frame["mean_obs"] = 90.0
    frame["mean_exp"] = 100.0

    row = _detect(frame, direction_override={"daily": ("mean_obs", "mean_exp")})

    assert row["daily_score"] > 0
    assert row["anomaly_direction"] == "low"


def test_streak_counts_elevated_days() -> None:
    score = pd.Series([3.0, 3.0, np.nan, 3.0, -0.5, 3.0, -3.0])

    streak = anomaly_streak_days(
        score,
        threshold=2.0,
        streak_tolerance_window_days=4,
        rolling_window_min_coverage=0.5,
    )

    assert np.isnan(streak.iloc[2])
    # Fenster von 4 Tagen ab Position 2: NaN / 3,0 / -0,5 / 3,0, der leicht negative Tag bricht nicht ab
    assert streak.iloc[5] == 2.0
    # -3,0 ist auffällig in Gegenrichtung, die Streak beginnt neu
    assert streak.iloc[6] == 1.0


def _level_shift_values(weekly: float, long_term: float) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    return pd.DataFrame({"weekly": weekly, "long_term": long_term}, index=index)


def _streaks(values: pd.DataFrame, min_sustained_scales: int) -> pd.DataFrame:
    return build_level_shift_streaks(
        values,
        streak_thresholds={"weekly": 1.0, "long_term": 20.0},
        sustained_anomaly_streak_days=6,
        min_sustained_scales=min_sustained_scales,
        streak_tolerance_window_days=7,
        rolling_window_min_coverage=0.8,
    )


def test_scale_sustained_after_streak() -> None:
    result = _streaks(_level_shift_values(3.0, 5.0), min_sustained_scales=2)

    assert not result["weekly_sustained"].iloc[4]
    assert result["weekly_sustained"].iloc[5]
    assert not result["long_term_sustained"].any()


def test_drift_needs_enough_scales() -> None:
    two_scales = _level_shift_values(3.0, 30.0)

    assert _streaks(two_scales, min_sustained_scales=2)["sustained_drift"].iloc[-1]
    assert not _streaks(two_scales, min_sustained_scales=3)["sustained_drift"].iloc[-1]
    one_scale = _level_shift_values(0.2, 30.0)
    assert not _streaks(one_scale, min_sustained_scales=2)["sustained_drift"].any()
