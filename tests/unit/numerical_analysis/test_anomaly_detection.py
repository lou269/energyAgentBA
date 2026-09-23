# python -m pytest tests/unit/numerical_analysis/test_anomaly_detection.py -v

from collections.abc import Mapping, Sequence

import pandas as pd
import pytest

from src.numerical_analysis.anomaly_detection import build_anomaly_detection


TRAIN_RESIDUALS = [-2.0, -1.0, 0.0, 1.0, 2.0] * 20

REFERENCE_COLUMNS = {
    "short_term": ("current_power", "trend_reference_mean"),
    "daily": ("current_power", "daily_expected"),
    "weekly": ("current_power", "weekly_expected"),
    "long_term": ("current_power", "long_term_mean"),
}

MIN_REFERENCE_SAMPLES = {"short_term": 50, "daily": 50, "weekday": 50, "weekly": 50, "long_term": 50}


def _analysis_frame(
    current_power: list[float],
    reference: float,
    split: list[str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "split": split,
            "current_power": current_power,
            "trend_reference_mean": reference,
            "daily_expected": reference,
            "weekly_expected": reference,
            "long_term_mean": reference,
        },
        index=pd.date_range("2013-01-01", periods=len(split), freq="h", tz="UTC"),
    )


def _detect(
    frame: pd.DataFrame,
    *,
    reference_columns: Mapping[str, tuple[str, str]] = REFERENCE_COLUMNS,
    gate_scales: Sequence[str] = tuple(REFERENCE_COLUMNS),
    direction_override_columns: Mapping[str, tuple[str, str]] = {},
    min_reference_samples: Mapping[str, int] = MIN_REFERENCE_SAMPLES,
    min_residual_std_w: float = 0.1,
    unusual_threshold: float = 2.0,
    streak_thresholds: Mapping[str, float] = {},
) -> pd.DataFrame:
    return build_anomaly_detection(
        frame,
        reference_columns=reference_columns,
        direction_override_columns=direction_override_columns,
        min_reference_samples=min_reference_samples,
        min_residual_std_w=min_residual_std_w,
        unusual_threshold=unusual_threshold,
        strong_anomaly_threshold=3.0,
        gate_scales=gate_scales,
        streak_thresholds=streak_thresholds,
        sustained_anomaly_streak_days=6,
        min_sustained_scales=2,
        streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
    )


def test_z_score_uses_only_train_residuals_for_calibration() -> None:
    reference = 100.0
    split = ["train"] * len(TRAIN_RESIDUALS) + ["test"]
    current_power = [reference + r for r in TRAIN_RESIDUALS] + [reference + 500.0]

    result = _detect(_analysis_frame(current_power, reference, split))

    expected_std = pd.Series(TRAIN_RESIDUALS).std()
    assert result["short_term_score"].iloc[-2] == pytest.approx(2.0 / expected_std)
    # der Test-Ausreisser darf Mittelwert/Std nicht verschoben haben, sonst wäre es keine echte Kalibrierung nur auf Trainingsdaten
    assert result["short_term_score"].iloc[-1] == pytest.approx(500.0 / expected_std)


def test_insufficient_reference_samples_yields_no_score() -> None:
    train_residuals = [-2.0, -1.0, 0.0, 1.0, 2.0] * 2
    reference = 100.0
    current_power = [reference + r for r in train_residuals]

    result = _detect(_analysis_frame(current_power, reference, ["train"] * len(train_residuals)))

    assert result["short_term_score"].isna().all()
    assert not result["short_term_sustained"].any()


def test_residual_std_below_floor_yields_no_score() -> None:
    noise = [0.001, -0.001] * 50
    reference = 100.0
    current_power = [reference + n for n in noise]

    result = _detect(_analysis_frame(current_power, reference, ["train"] * len(noise)), min_residual_std_w=1.0)

    # winzige, aber von Null verschiedene Streuung - darf keinen (potenziell riesigen) Z-Score liefern
    assert result["short_term_score"].isna().all()


def _frame_with_largest_weekly_deviation() -> pd.DataFrame:
    n = len(TRAIN_RESIDUALS)

    return pd.DataFrame(
        {
            "split": ["train"] * n + ["test"],
            "current_power": [100.0 + r for r in TRAIN_RESIDUALS] + [106.0],
            "trend_reference_mean": [100.0] * n + [104.0],
            "daily_expected": [100.0] * n + [106.0],
            "weekly_expected": [100.0] * n + [100.0],
            "long_term_mean": [100.0] * n + [106.0],
        },
        index=pd.date_range("2013-01-01", periods=n + 1, freq="h", tz="UTC"),
    )


def test_dominant_scale_picks_largest_absolute_score() -> None:
    row = _detect(_frame_with_largest_weekly_deviation()).iloc[-1]

    # weekly hat den größten Ausschlag (+6 W bei identischer Trainingsstreuung wie die anderen drei Skalen) und muss deshalb den Gesamt-Score und die Einstufung bestimmen
    assert row["dominant_scale"] == "weekly"
    assert row["anomaly_direction"] == "high"
    assert row["anomaly_level"] == "strong_anomaly"
    assert row["anomaly_score"] == pytest.approx(row["weekly_score"])


def test_scales_outside_the_gate_do_not_set_score_or_level() -> None:
    row = _detect(_frame_with_largest_weekly_deviation(), gate_scales=("short_term", "daily")).iloc[-1]

    # weekly bleibt der größte Ausschlag, zählt fürs Gate aber nicht mehr mit
    assert abs(row["weekly_score"]) > abs(row["short_term_score"])
    assert row["dominant_scale"] == "short_term"
    assert row["anomaly_score"] == pytest.approx(row["short_term_score"])
    assert row["anomaly_level"] == "normal"


def test_slow_scales_open_the_gate_through_their_own_streak_threshold() -> None:
    n = len(TRAIN_RESIDUALS)
    drift_days = 7

    frame = pd.DataFrame(
        {
            "split": ["train"] * n + ["test"] * drift_days,
            "current_power": [100.0 + r for r in TRAIN_RESIDUALS] + [100.0] * drift_days,
            "daily_expected": 100.0,
            "weekday_expected": 100.0,
            # z ca. 2,1 bzw. 1,4, beides unter unusual_threshold
            "weekly_expected": [100.0] * n + [97.0] * drift_days,
            "long_term_mean": [100.0] * n + [98.0] * drift_days,
        },
        index=pd.date_range("2013-01-01", periods=n + drift_days, freq="h", tz="UTC"),
    )
    reference_columns = {
        "daily": ("current_power", "daily_expected"),
        "weekday": ("current_power", "weekday_expected"),
        "weekly": ("current_power", "weekly_expected"),
        "long_term": ("current_power", "long_term_mean"),
    }

    result = _detect(
        frame,
        unusual_threshold=2.6,
        gate_scales=("daily", "weekday"),
        streak_thresholds={"weekly": 1.25, "long_term": 1.0},
        reference_columns=reference_columns,
    )
    row = result.iloc[-1]

    assert row["anomaly_level"] == "normal"
    assert row["weekly_sustained"] and row["long_term_sustained"]
    assert row["sustained_drift"]

    # mit unusual_threshold als Streak-Schwelle wäre dieselbe Drift unsichtbar
    without_own_thresholds = _detect(frame, unusual_threshold=2.6, gate_scales=("daily", "weekday"), reference_columns=reference_columns)
    assert not without_own_thresholds["sustained_drift"].iloc[-1]


def test_reference_columns_parameter_restricts_scales() -> None:
    reference = 100.0
    split = ["train"] * len(TRAIN_RESIDUALS) + ["test"]
    current_power = [reference + r for r in TRAIN_RESIDUALS] + [reference + 500.0]

    result = _detect(
        _analysis_frame(current_power, reference, split),
        gate_scales=("daily", "weekly", "long_term"),
        reference_columns={
            "daily": ("current_power", "daily_expected"),
            "weekly": ("current_power", "weekly_expected"),
            "long_term": ("current_power", "long_term_mean"),
        },
    )

    assert "short_term_score" not in result.columns
    assert result["dominant_scale"].iloc[-1] in ("daily", "weekly", "long_term")


def test_min_reference_samples_disables_only_the_affected_scale() -> None:
    reference = 100.0
    split = ["train"] * len(TRAIN_RESIDUALS) + ["test"]
    current_power = [reference + r for r in TRAIN_RESIDUALS] + [reference + 500.0]

    # short_term bekommt eine unerreichbar hohe Schwelle, die anderen drei bleiben bei 50 (erreicht)
    result = _detect(
        _analysis_frame(current_power, reference, split),
        min_reference_samples={"short_term": 1000, "daily": 50, "weekly": 50, "long_term": 50},
    )

    assert result["short_term_score"].isna().all()
    assert result["daily_score"].notna().any()


def test_direction_override_column_replaces_the_scores_own_sign_for_direction() -> None:
    n = len(TRAIN_RESIDUALS)
    split = ["train"] * n + ["test"]
    # der Score-Ausschlag ist negativ (current_power < daily_expected), die Override-Spalten
    # zeigen aber eine positive Abweichung, direction muss Override-Spalte folgen, nicht dem Score
    current_power = [100.0 + r for r in TRAIN_RESIDUALS] + [90.0]

    frame = pd.DataFrame(
        {
            "split": split,
            "current_power": current_power,
            "trend_reference_mean": [100.0] * n + [100.0],
            "daily_expected": [100.0] * n + [100.0],
            "today_mean": [100.0] * n + [90.0],
            "today_mean_expected": [100.0] * n + [80.0],
        },
        index=pd.date_range("2013-01-01", periods=n + 1, freq="h", tz="UTC"),
    )

    result = _detect(
        frame,
        gate_scales=("daily",),
        reference_columns={"daily": ("current_power", "daily_expected")},
        direction_override_columns={"daily": ("today_mean", "today_mean_expected")},
    )

    row = result.iloc[-1]
    assert row["daily_score"] < 0
    assert row["dominant_scale"] == "daily"
    # today_mean (90) > today_mean_expected (80) -> "high", trotz negativem daily_score
    assert row["anomaly_direction"] == "high"