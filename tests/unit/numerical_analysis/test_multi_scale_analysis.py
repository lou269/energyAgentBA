# python -m pytest tests/unit/numerical_analysis/test_multi_scale_analysis.py -v



import pandas as pd
import pytest

from src.numerical_analysis.multi_scale_analysis import build_multi_scale_analysis


def test_daily_expected_is_causal_and_excludes_current_row() -> None:
    train_index = pd.date_range("2020-01-01", periods=5, freq="1D", tz="UTC")
    train = pd.DataFrame({"p": [10.0, 10.0, 10.0, 10.0, 100.0]}, index=train_index)
    validation = pd.DataFrame({"p": [10.0]}, index=pd.date_range("2020-01-06", periods=1, freq="1D", tz="UTC"))
    test = pd.DataFrame({"p": [10.0]}, index=pd.date_range("2020-01-07", periods=1, freq="1D", tz="UTC"))

    result = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=1, sample_period_hours=24.0, long_term_window=1,
        min_daily_reference_samples=2, min_weekly_reference_samples=2,
        trend_threshold=0.1, min_reference_power_w=0.0,
        local_timezone="UTC",
    )

    # letzter Trainingstag hat einen Ausreisser (100 statt 10) - der kausale Referenzwert
    # für diese Zeile darf ihn nicht selbst enthalten, sonst würde er sich selbst verdecken
    assert result.loc[train_index[-1], "daily_expected"] == pytest.approx(10.0)
    # Validation liegt komplett nach dem Training -> darf den vollen Trainingsdurchschnitt nutzen
    assert result.loc[pd.Timestamp("2020-01-06", tz="UTC"), "daily_expected"] == pytest.approx(28.0)


def test_trend_slope_matches_known_linear_ramp() -> None:
    idx = pd.date_range("2020-01-01", periods=10, freq="1h", tz="UTC")
    train = pd.DataFrame({"p": [float(i) * 10.0 for i in range(10)]}, index=idx)
    validation = pd.DataFrame({"p": [90.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=1), periods=1, freq="1h"))
    test = pd.DataFrame({"p": [100.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=2), periods=1, freq="1h"))

    result = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=5, sample_period_hours=1.0, long_term_window=5,
        min_daily_reference_samples=1, min_weekly_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        local_timezone="UTC",
    )

    slope = result["trend_slope_w_per_hour"].dropna()
    # Rampe steigt exakt 10 W pro Stunde -> die Regressionssteigung muss das treffen
    assert slope.iloc[0] == pytest.approx(10.0)
    assert result.loc[slope.index[0], "trend"] == "increasing"


def test_trend_change_is_nan_when_reference_below_floor() -> None:
    idx = pd.date_range("2020-01-01", periods=6, freq="1h", tz="UTC")
    train = pd.DataFrame({"p": [5.0] * 6}, index=idx)
    validation = pd.DataFrame({"p": [5.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=1), periods=1, freq="1h"))
    test = pd.DataFrame({"p": [5.0]}, index=pd.date_range(idx[-1] + pd.Timedelta(hours=2), periods=1, freq="1h"))

    with_floor = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=2, sample_period_hours=1.0, long_term_window=2,
        min_daily_reference_samples=1, min_weekly_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=10.0,
        local_timezone="UTC",
    )
    without_floor = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=2, sample_period_hours=1.0, long_term_window=2,
        min_daily_reference_samples=1, min_weekly_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        local_timezone="UTC",
    )

    # Referenzwert liegt konstant bei 5 W -> unter der 10-W-Schwelle ist trend_change nicht auswertbar
    assert with_floor["trend_change"].notna().sum() == 0
    assert without_floor["trend_change"].notna().sum() > 0


def test_daily_profile_groups_by_local_hour_across_a_dst_transition() -> None:
    # 09:00 UTC an sechs Tagen rund um die britische Sommerzeit-Umstellung (29.03.2020)
    train_index = pd.DatetimeIndex(
        [
            "2020-03-26 09:00:00+00:00",
            "2020-03-27 09:00:00+00:00",
            "2020-03-28 09:00:00+00:00",
            "2020-03-30 09:00:00+00:00",
            "2020-03-31 09:00:00+00:00",
            "2020-04-01 09:00:00+00:00",
        ],
        tz="UTC",
    )
    # vor der Umstellung (lokal 09:00) konstant 10 W, danach (lokal 10:00) konstant 50 W
    train = pd.DataFrame({"p": [10.0, 10.0, 10.0, 50.0, 50.0, 50.0]}, index=train_index)
    validation = pd.DataFrame(
        {"p": [50.0]}, index=pd.date_range("2020-04-02 09:00:00+00:00", periods=1, freq="1D")
    )
    test = pd.DataFrame(
        {"p": [50.0]}, index=pd.date_range("2020-04-03 09:00:00+00:00", periods=1, freq="1D")
    )

    result = build_multi_scale_analysis(
        train, validation, test, "p",
        short_term_window=1, sample_period_hours=24.0, long_term_window=1,
        min_daily_reference_samples=2, min_weekly_reference_samples=2,
        trend_threshold=0.1, min_reference_power_w=0.0,
        local_timezone="Europe/London",
    )


    assert result.loc[validation.index[0], "daily_expected"] == pytest.approx(50.0)
