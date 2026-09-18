# python -m pytest tests/unit/numerical_analysis/test_multi_scale_analysis.py -v



import pandas as pd
import pytest

from src.numerical_analysis.multi_scale_analysis import build_daily_cycle_analysis, build_multi_scale_analysis


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


def test_build_daily_cycle_analysis_resamples_hourly_history_and_splits_on_reference_window_end() -> None:
    index = pd.date_range("2020-01-01", periods=24 * 7, freq="1h", tz="UTC")
    history = pd.Series(100.0, index=index, name="p")

    # 2020-01-05 nur bis 12:00 beobachtet -> Tag gilt als nicht abgeschlossen, fällt ganz aus dem Training
    reference_window_end = pd.Timestamp("2020-01-05T12:00:00Z")

    result = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=2,
        weekly_window_days=2,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    assert len(result) == 7
    assert result.loc[pd.Timestamp("2020-01-04", tz="UTC"), "split"] == "train"
    assert result.loc[pd.Timestamp("2020-01-05", tz="UTC"), "split"] == "validation"
    assert result.loc[pd.Timestamp("2020-01-06", tz="UTC"), "split"] == "validation"
    assert result.loc[pd.Timestamp("2020-01-07", tz="UTC"), "split"] == "test"
    assert result.loc[pd.Timestamp("2020-01-04", tz="UTC"), "today_mean"] == pytest.approx(100.0)


def test_build_daily_cycle_analysis_daily_std_expected_is_causal_and_frozen_after_train() -> None:
    index = pd.date_range("2020-01-01", periods=24 * 7, freq="1h", tz="UTC")
    # Tage 5-7 (validation/test) haben absichtlich eine viel höhere Streuung als das Training
    day_amplitudes = [1.0, 2.0, 3.0, 4.0, 40.0, 40.0, 40.0]
    values = [
        100.0 + (amplitude if hour % 2 == 0 else -amplitude)
        for amplitude in day_amplitudes
        for hour in range(24)
    ]
    history = pd.Series(values, index=index, name="p")

    reference_window_end = pd.Timestamp("2020-01-05T12:00:00Z")

    result = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=2,
        weekly_window_days=2,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    daily_std = history.resample("D").std(ddof=0)
    # Training läuft bis einschliesslich Tag 4 (reference_window_end liegt am 5.) - Tag 4 selbst darf in seiner eigenen Referenz nicht auftauchen, die eingefrorene Referenz danach schon
    expected_last_train_day_reference = daily_std.loc[[
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2020-01-02", tz="UTC"),
        pd.Timestamp("2020-01-03", tz="UTC"),
    ]].mean()
    expected_frozen_reference = daily_std.loc[[
        pd.Timestamp("2020-01-01", tz="UTC"),
        pd.Timestamp("2020-01-02", tz="UTC"),
        pd.Timestamp("2020-01-03", tz="UTC"),
        pd.Timestamp("2020-01-04", tz="UTC"),
    ]].mean()

    assert pd.isna(result.loc[pd.Timestamp("2020-01-01", tz="UTC"), "daily_std_expected"])
    # letzter Trainingstag: Referenz ist der Mittelwert der Vortage, der Tag selbst darf nicht einfließen
    assert result.loc[pd.Timestamp("2020-01-04", tz="UTC"), "daily_std_expected"] == pytest.approx(expected_last_train_day_reference)
    # validation/test: eingefroren auf den vollen Trainingsdurchschnitt, die eigene (viel größere) Streuung fließt nicht ein
    assert result.loc[pd.Timestamp("2020-01-05", tz="UTC"), "daily_std_expected"] == pytest.approx(expected_frozen_reference)
    assert result.loc[pd.Timestamp("2020-01-07", tz="UTC"), "daily_std_expected"] == pytest.approx(expected_frozen_reference)

    assert result.loc[pd.Timestamp("2020-01-07", tz="UTC"), "daily_std"] == pytest.approx(daily_std.loc[pd.Timestamp("2020-01-07", tz="UTC")])


def test_build_daily_cycle_analysis_today_mean_expected_is_causal_and_frozen_after_train() -> None:
    index = pd.date_range("2020-01-01", periods=24 * 7, freq="1h", tz="UTC")
    day_levels = [100.0, 102.0, 98.0, 101.0, 500.0, 500.0, 500.0]
    values = [level for level in day_levels for _ in range(24)]
    history = pd.Series(values, index=index, name="p")

    reference_window_end = pd.Timestamp("2020-01-05T12:00:00Z")

    result = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=2,
        weekly_window_days=2,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    daily_mean = history.resample("D").mean()
    train_days = [pd.Timestamp(d, tz="UTC") for d in ("2020-01-01", "2020-01-02", "2020-01-03")]

    assert pd.isna(result.loc[pd.Timestamp("2020-01-01", tz="UTC"), "today_mean_expected"])
    # letzter Trainingstag (04.): Referenz ist der Mittelwert der drei Vortage, ohne den Tag selbst
    assert result.loc[pd.Timestamp("2020-01-04", tz="UTC"), "today_mean_expected"] == pytest.approx(
        daily_mean.loc[train_days].mean()
    )
    # validation/test: eingefroren auf den vollen Trainingsdurchschnitt (Tag 1-4), unabhängig vom Sprung auf 500
    expected_frozen = daily_mean.loc[[*train_days, pd.Timestamp("2020-01-04", tz="UTC")]].mean()
    assert result.loc[pd.Timestamp("2020-01-05", tz="UTC"), "today_mean_expected"] == pytest.approx(expected_frozen)
    assert result.loc[pd.Timestamp("2020-01-07", tz="UTC"), "today_mean_expected"] == pytest.approx(expected_frozen)


def test_build_daily_cycle_analysis_weekly_mean_is_a_contemporary_rolling_window_over_today_mean() -> None:
    index = pd.date_range("2020-01-01", periods=24 * 10, freq="1h", tz="UTC")
    day_levels = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0]
    values = [level for level in day_levels for _ in range(24)]
    history = pd.Series(values, index=index, name="p")

    reference_window_end = pd.Timestamp("2020-01-08T12:00:00Z")

    result = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=3,
        weekly_window_days=3,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    daily_mean = history.resample("D").mean()
    expected_weekly_mean = daily_mean.rolling(window=3, min_periods=3).mean()


    pd.testing.assert_series_equal(
        result["weekly_mean"], expected_weekly_mean, check_names=False,
    )

    train_index = [pd.Timestamp(d, tz="UTC") for d in ("2020-01-03", "2020-01-04", "2020-01-05", "2020-01-06", "2020-01-07")]
    expected_frozen = expected_weekly_mean.loc[train_index].mean()

    assert pd.isna(result.loc[pd.Timestamp("2020-01-03", tz="UTC"), "weekly_mean_expected"])
    # letzter Trainingstag: Referenz ist der Mittelwert der Vortage, der Tag selbst darf nicht einfliessen
    assert result.loc[pd.Timestamp("2020-01-07", tz="UTC"), "weekly_mean_expected"] == pytest.approx(
        expected_weekly_mean.loc[train_index[:-1]].mean()
    )
    # validation/test: eingefroren auf den vollen Trainingsdurchschnitt
    assert result.loc[pd.Timestamp("2020-01-08", tz="UTC"), "weekly_mean_expected"] == pytest.approx(expected_frozen)
    assert result.loc[pd.Timestamp("2020-01-10", tz="UTC"), "weekly_mean_expected"] == pytest.approx(expected_frozen)


def test_build_daily_cycle_analysis_long_term_window_mean_gets_its_own_frozen_reference() -> None:
    index = pd.date_range("2020-01-01", periods=24 * 10, freq="1h", tz="UTC")
    day_levels = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0]
    values = [level for level in day_levels for _ in range(24)]
    history = pd.Series(values, index=index, name="p")

    reference_window_end = pd.Timestamp("2020-01-08T12:00:00Z")

    result = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=4,
        weekly_window_days=2,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    daily_mean = history.resample("D").mean()
    expected_long_term_window_mean = daily_mean.rolling(window=4, min_periods=4).mean()

    pd.testing.assert_series_equal(result["long_term_window_mean"], expected_long_term_window_mean, check_names=False)

    train_index = [pd.Timestamp(d, tz="UTC") for d in ("2020-01-04", "2020-01-05", "2020-01-06", "2020-01-07")]

    assert result.loc[pd.Timestamp("2020-01-07", tz="UTC"), "long_term_expected"] == pytest.approx(
        expected_long_term_window_mean.loc[train_index[:-1]].mean()
    )
    expected_frozen = expected_long_term_window_mean.loc[train_index].mean()
    assert result.loc[pd.Timestamp("2020-01-08", tz="UTC"), "long_term_expected"] == pytest.approx(expected_frozen)
    assert result.loc[pd.Timestamp("2020-01-10", tz="UTC"), "long_term_expected"] == pytest.approx(expected_frozen)


def test_weekly_mean_tolerates_a_single_missing_day_within_the_window() -> None:
    index = pd.date_range("2020-01-01", periods=24 * 10, freq="1h", tz="UTC")
    # Tag 5 (05.01.) fehlt komplett, z.B. wegen exclude_incomplete_days() vorgelagert in der Preprocessing-Stufe
    day_levels = [100.0, 110.0, 120.0, 130.0, float("nan"), 150.0, 160.0, 170.0, 180.0, 190.0]
    values = [level for level in day_levels for _ in range(24)]
    history = pd.Series(values, index=index, name="p")

    reference_window_end = pd.Timestamp("2020-01-08T12:00:00Z")

    result = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=5,
        weekly_window_days=5,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=0.8,
        local_timezone="UTC",
    )

    # Fenster 04.-08.01. enthält genau den einen NaN-Tag -> min_periods=ceil(5*0.8)=4, mit 4 gültigen Tagen also kein Totalausfall
    assert result.loc[pd.Timestamp("2020-01-08", tz="UTC"), "weekly_mean"] == pytest.approx((130.0 + 150.0 + 160.0 + 170.0) / 4)

    # Kontrollprobe: mit voller Abdeckung (altes Verhalten) reißt derselbe eine NaN-Tag das ganze Fenster
    strict = build_daily_cycle_analysis(
        history,
        reference_window_end=reference_window_end,
        short_term_window=2, sample_period_hours=24.0, long_term_window=5,
        weekly_window_days=5,
        min_weekday_reference_samples=1,
        trend_threshold=0.1, min_reference_power_w=0.0,
        rolling_window_min_coverage=1.0,
        local_timezone="UTC",
    )

    assert pd.isna(strict.loc[pd.Timestamp("2020-01-08", tz="UTC"), "weekly_mean"])
