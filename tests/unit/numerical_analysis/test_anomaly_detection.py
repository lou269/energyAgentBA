# python -m pytest tests/unit/numerical_analysis/test_anomaly_detection.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.numerical_analysis.anomaly_detection import aggregate_daily_anomaly, build_anomaly_detection


def _analysis_frame(
    current_power: list[float],
    reference: float,
    split: list[str]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "split": split,
            "current_power": current_power,
            "short_term_mean": reference,
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
        sample_period_hours=1.0,
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
        sample_period_hours=1.0,
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
        sample_period_hours=1.0,
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
                "short_term_mean": [100.0] * n + [104.0],
                "daily_expected": [100.0] * n + [106.0],
                "weekly_expected": [100.0] * n + [100.0],
                "long_term_mean": [100.0] * n + [106.0],
            },
            index=pd.date_range("2013-01-01", periods=n + 1, freq="h", tz="UTC"),
        ),
        min_reference_samples=50, min_residual_std_w=0.1,
        unusual_threshold=2.0, strong_anomaly_threshold=3.0,
        sample_period_hours=1.0,
    )

    row = result.iloc[-1]
    # weekly hat den größten Ausschlag (+6 W bei identischer Trainingsstreuung wie die anderen drei Skalen) und muss deshalb den Gesamt-Score und die Einstufung bestimmen
    assert row["dominant_scale"] == "weekly"
    assert row["anomaly_direction"] == "high"
    assert row["anomaly_level"] == "strong_anomaly"
    assert row["anomaly_score"] == pytest.approx(row["weekly_score"])


def _scores(values: dict[str, list[float | None]], start: str = "2013-01-01") -> pd.DataFrame:
    n = len(next(iter(values.values())))
    index = pd.date_range(start, periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {f"{scale}_score": series for scale, series in values.items()},
        index=index,
    )


def test_daily_aggregate_uses_the_windows_peak_not_the_last_hour() -> None:
    # Peak liegt 3h vor target_timestamp - der reine Einzelstunden-Blick hätte das komplett verpasst
    anomaly = _scores(
        {
            "short_term": [0.5, 0.6, 4.2, 0.4, 0.3, 0.2],
            "daily": [0.1] * 6,
            "weekly": [0.1] * 6,
            "long_term": [0.1] * 6,
        }
    )
    target_timestamp = anomaly.index[-1]

    summary = aggregate_daily_anomaly(
        anomaly,
        target_timestamp=target_timestamp,
        window_hours=24,
        sample_period_hours=1.0,
        unusual_threshold=2.0,
        strong_anomaly_threshold=3.0,
    )

    assert summary["dominant_scale"] == "short_term"
    assert summary["anomaly_score"] == pytest.approx(4.2)
    assert summary["anomaly_level"] == "strong_anomaly"
    assert summary["anomaly_peak_timestamp"] == anomaly.index[2]
    assert summary["short_term_score"] == pytest.approx(4.2)


def test_daily_aggregate_counts_all_elevated_hours_not_just_a_streak() -> None:
    # auffällig, normal, auffällig, auffällig - ein reiner Streak-Zähler würde bei der Lücke auf 0 zurückfallen
    anomaly = _scores(
        {
            "short_term": [2.5, 0.1, 2.5, 2.5],
            "daily": [0.1] * 4,
            "weekly": [0.1] * 4,
            "long_term": [0.1] * 4,
        }
    )
    target_timestamp = anomaly.index[-1]

    summary = aggregate_daily_anomaly(
        anomaly,
        target_timestamp=target_timestamp,
        window_hours=24,
        sample_period_hours=1.0,
        unusual_threshold=2.0,
        strong_anomaly_threshold=3.0,
    )

    assert summary["short_term_elevated_hours"] == pytest.approx(3.0)


def test_daily_aggregate_ignores_hours_outside_the_window() -> None:
    # riesiger Ausreisser liegt eine Stunde vor dem 3h-Fenster -> darf die Aggregation nicht beeinflussen
    anomaly = _scores(
        {
            "short_term": [9.0, 0.2, 0.3, 0.4],
            "daily": [0.1] * 4,
            "weekly": [0.1] * 4,
            "long_term": [0.1] * 4,
        }
    )
    target_timestamp = anomaly.index[-1]

    summary = aggregate_daily_anomaly(
        anomaly,
        target_timestamp=target_timestamp,
        window_hours=3,
        sample_period_hours=1.0,
        unusual_threshold=2.0,
        strong_anomaly_threshold=3.0,
    )

    assert summary["anomaly_score"] == pytest.approx(0.4)
    assert summary["anomaly_level"] == "normal"


def test_daily_aggregate_is_null_when_no_scale_has_a_score_in_the_window() -> None:
    anomaly = _scores(
        {
            "short_term": [None, None, None],
            "daily": [None, None, None],
            "weekly": [None, None, None],
            "long_term": [None, None, None],
        }
    )
    target_timestamp = anomaly.index[-1]

    summary = aggregate_daily_anomaly(
        anomaly,
        target_timestamp=target_timestamp,
        window_hours=24,
        sample_period_hours=1.0,
        unusual_threshold=2.0,
        strong_anomaly_threshold=3.0,
    )

    assert pd.isna(summary["anomaly_score"]) # type: ignore
    assert pd.isna(summary["dominant_scale"]) # type: ignore
    assert pd.isna(summary["anomaly_level"]) # type: ignore
    assert pd.isna(summary["anomaly_peak_timestamp"]) # type: ignore