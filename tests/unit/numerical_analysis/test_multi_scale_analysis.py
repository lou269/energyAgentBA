# python -m pytest tests/unit/numerical_analysis/test_multi_scale_analysis.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis


def test_daily_expected_is_causal_and_excludes_current_row() -> None:
    train_index = pd.date_range("2020-01-01", periods=5, freq="1D")
    train = pd.DataFrame({"p": [10.0, 10.0, 10.0, 10.0, 100.0]}, index=train_index)
    validation = pd.DataFrame({"p": [10.0]}, index=pd.date_range("2020-01-06", periods=1, freq="1D"))
    test = pd.DataFrame({"p": [10.0]}, index=pd.date_range("2020-01-07", periods=1, freq="1D"))

    result = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=1, sample_period_hours=24.0, long_term_window=1,
        min_daily_reference_samples=2, min_weekly_reference_samples=2,
        trend_threshold=0.1, min_reference_power_w=0.0,
    )

    # letzter Trainingstag hat einen Ausreisser (100 statt 10) - der kausale Referenzwert 
    # für diese Zeile darf ihn nicht selbst enthalten, sonst würde er sich selbst verdecken
    assert result.loc[train_index[-1], "daily_expected"] == pytest.approx(10.0)
    # Validation liegt komplett nach dem Training -> darf den vollen Trainingsdurchschnitt nutzen
    assert result.loc[pd.Timestamp("2020-01-06"), "daily_expected"] == pytest.approx(28.0)


def test_trend_slope_matches_known_linear_ramp() -> None:
    idx = pd.date_range("2020-01-01", periods=10, freq="1h")
    train = pd.DataFrame({"p": [float(i) * 10.0 for i in range(10)]}, index=idx)
    validation = pd.DataFrame({"p": [90.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=1), periods=1, freq="1h"))
    test = pd.DataFrame({"p": [100.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=2), periods=1, freq="1h"))

    result = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=5, sample_period_hours=1.0, long_term_window=5,
        min_daily_reference_samples=1, min_weekly_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
    )

    slope = result["trend_slope_w_per_hour"].dropna()
    # Rampe steigt exakt 10 W pro Stunde -> die Regressionssteigung muss das treffen
    assert slope.iloc[0] == pytest.approx(10.0)
    assert result.loc[slope.index[0], "trend"] == "increasing"


def test_trend_change_is_nan_when_reference_below_floor() -> None:
    idx = pd.date_range("2020-01-01", periods=6, freq="1h")
    train = pd.DataFrame({"p": [5.0] * 6}, index=idx)
    validation = pd.DataFrame({"p": [5.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=1), periods=1, freq="1h"))
    test = pd.DataFrame({"p": [5.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=2), periods=1, freq="1h"))

    with_floor = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=2, sample_period_hours=1.0, long_term_window=2,
        min_daily_reference_samples=1, min_weekly_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=10.0,
    )
    without_floor = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=2, sample_period_hours=1.0, long_term_window=2,
        min_daily_reference_samples=1, min_weekly_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
    )

    # Referenzwert liegt konstant bei 5 W -> unter der 10-W-Schwelle ist trend_change nicht auswertbar
    assert with_floor["trend_change"].notna().sum() == 0
    assert without_floor["trend_change"].notna().sum() > 0
