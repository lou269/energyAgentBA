# python -m pytest tests/unit/numerical_analysis/test_anomaly_detection.py -v

import pandas as pd
import pytest

from src.numerical_analysis.anomaly_detection import build_anomaly_detection


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


def test_z_score_uses_only_train_residuals_for_calibration() -> None:
    train_residuals = [-2.0, -1.0, 0.0, 1.0, 2.0] * 20
    reference = 100.0
    split = ["train"] * len(train_residuals) + ["test"]
    current_power = [reference + r for r in train_residuals] + [reference + 500.0]

    result = build_anomaly_detection(
        _analysis_frame(current_power, reference, split),
        min_reference_samples=50, min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    expected_std = pd.Series(train_residuals).std()
    assert result["short_term_score"].iloc[-2] == pytest.approx(2.0 / expected_std)
    # der Test-Ausreisser darf Mittelwert/Std nicht verschoben haben, sonst wäre es keine echte Kalibrierung nur auf Trainingsdaten
    assert result["short_term_score"].iloc[-1] == pytest.approx(500.0 / expected_std)


def test_insufficient_reference_samples_yields_no_score() -> None:
    train_residuals = [-2.0, -1.0, 0.0, 1.0, 2.0] * 2
    reference = 100.0
    current_power = [reference + r for r in train_residuals]

    result = build_anomaly_detection(
        _analysis_frame(current_power, reference, ["train"] * len(train_residuals)),
        min_reference_samples=50, min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    assert result["short_term_score"].isna().all()


def test_residual_std_below_floor_yields_no_score() -> None:
    noise = [0.001, -0.001] * 50
    reference = 100.0
    current_power = [reference + n for n in noise]

    result = build_anomaly_detection(
        _analysis_frame(current_power, reference, ["train"] * len(noise)),
        min_reference_samples=50, min_residual_std_w=1.0,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    # winzige, aber von Null verschiedene Streuung - darf keinen (potenziell riesigen) Z-Score liefern
    assert result["short_term_score"].isna().all()


def test_dominant_scale_picks_largest_absolute_score() -> None:
    train_pattern = [-2.0, -1.0, 0.0, 1.0, 2.0] * 20
    n = len(train_pattern)
    split = ["train"] * n + ["test"]

    result = build_anomaly_detection(
        pd.DataFrame(
            {
                "split": split,
                "current_power": [100.0 + r for r in train_pattern] + [106.0],
                "trend_reference_mean": [100.0] * n + [104.0],
                "daily_expected": [100.0] * n + [106.0],
                "weekly_expected": [100.0] * n + [100.0],
                "long_term_mean": [100.0] * n + [106.0],
            },
            index=pd.date_range("2013-01-01", periods=n + 1, freq="h", tz="UTC"),
        ),
        min_reference_samples=50, min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    row = result.iloc[-1]
    # weekly hat den größten Ausschlag (+6 W bei identischer Trainingsstreuung wie die anderen drei Skalen) und muss deshalb den Gesamt-Score und die Einstufung bestimmen
    assert row["dominant_scale"] == "weekly"
    assert row["anomaly_direction"] == "high"
    assert row["anomaly_level"] == "strong_anomaly"
    assert row["anomaly_score"] == pytest.approx(row["weekly_score"])


def test_elevated_hours_resets_at_local_not_utc_midnight() -> None:
    
    calibration_index = pd.date_range("2020-06-01", periods=20, freq="h", tz="UTC")
    calibration_power = [100.0 + (0.01 if i % 2 == 0 else -0.01) for i in range(20)]

    dst_index = pd.DatetimeIndex(
        [
            "2020-06-13 22:00:00+00:00",
            "2020-06-13 23:00:00+00:00",
            "2020-06-14 00:00:00+00:00",
            "2020-06-14 01:00:00+00:00",
        ],
        tz="UTC",
    )
    dst_power = [150.0, 150.0, 150.0, 150.0]

    index = calibration_index.append(dst_index)
    current_power = calibration_power + dst_power
    split = ["train"] * len(index)

    frame = pd.DataFrame(
        {
            "split": split,
            "current_power": current_power,
            "trend_reference_mean": 100.0,
            "daily_expected": 100.0,
            "weekly_expected": 100.0,
            "long_term_mean": 100.0,
        },
        index=index,
    )

    result = build_anomaly_detection(
        frame,
        min_reference_samples=20, min_residual_std_w=0.001,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="Europe/London",
    )

    elevated = result.loc[dst_index, "short_term_elevated_hours"]
    # lokaler Tageswechsel liegt zwischen 23:00 und 00:00 UTC (BST = UTC+1) -> Zähler muss dort auf 1 zurückfallen, 
    # nicht erst eine Stunde später bei 00:00 UTC
    assert elevated.tolist() == pytest.approx([1.0, 1.0, 2.0, 3.0])


def test_reference_columns_parameter_restricts_scales() -> None:
    train_residuals = [-2.0, -1.0, 0.0, 1.0, 2.0] * 20
    reference = 100.0
    split = ["train"] * len(train_residuals) + ["test"]
    current_power = [reference + r for r in train_residuals] + [reference + 500.0]

    result = build_anomaly_detection(
        _analysis_frame(current_power, reference, split),
        min_reference_samples=50, min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
        reference_columns={
            "daily": ("current_power", "daily_expected"),
            "weekly": ("current_power", "weekly_expected"),
            "long_term": ("current_power", "long_term_mean"),
        },
    )

    assert "short_term_score" not in result.columns
    assert result["dominant_scale"].iloc[-1] in ("daily", "weekly", "long_term")


def test_min_reference_samples_accepts_a_per_scale_mapping() -> None:
    train_residuals = [-2.0, -1.0, 0.0, 1.0, 2.0] * 20
    reference = 100.0
    split = ["train"] * len(train_residuals) + ["test"]
    current_power = [reference + r for r in train_residuals] + [reference + 500.0]

    frame = _analysis_frame(current_power, reference, split)

    # short_term bekommt eine unerreichbar hohe Schwelle, die anderen drei bleiben bei 50 (erreicht)
    result = build_anomaly_detection(
        frame,
        min_reference_samples={"short_term": 1000, "daily": 50, "weekly": 50, "long_term": 50},
        min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    assert result["short_term_score"].isna().all()
    assert result["daily_score"].notna().any()


def test_direction_override_column_replaces_the_scores_own_sign_for_direction() -> None:
    train_residuals = [-2.0, -1.0, 0.0, 1.0, 2.0] * 20
    n = len(train_residuals)
    split = ["train"] * n + ["test"]
    # der Score-Ausschlag ist negativ (current_power < daily_expected), die Override-Spalten
    # zeigen aber eine positive Abweichung, direction muss Override-Spalte folgen, nicht dem Score
    current_power = [100.0 + r for r in train_residuals] + [90.0]

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

    result = build_anomaly_detection(
        frame,
        min_reference_samples=50, min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0, streak_tolerance_window_days=7,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
        reference_columns={"daily": ("current_power", "daily_expected")},
        direction_override_columns={"daily": ("today_mean", "today_mean_expected")},
    )

    row = result.iloc[-1]
    assert row["daily_score"] < 0
    assert row["dominant_scale"] == "daily"
    # today_mean (90) > today_mean_expected (80) -> "high", trotz negativem daily_score
    assert row["anomaly_direction"] == "high"