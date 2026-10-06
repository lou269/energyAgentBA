# python -m pytest tests/unit/forecasting/test_prophet_model.py -v

import numpy as np
import pandas as pd
import pytest

from src.forecasting.prophet_model import (
    _prepare_prophet_data,
    absence_holidays,
    build_prophet_forecast,
    fit_prophet_model,
    is_refit_required,
)


def _history(values: list[float], start: str = "2020-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)


def _fit(
    history: pd.Series,
    country_holidays: str | None = None,
    local_timezone: str = "UTC",
    log_transform: bool = False,
    level_shift_start: pd.Timestamp | None = None,
    absence_windows: tuple[tuple[pd.Timestamp, pd.Timestamp], ...] = (),
):
    return fit_prophet_model(
        history,
        growth="linear",
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
        country_holidays=country_holidays,
        local_timezone=local_timezone,
        log_transform=log_transform,
        interval_width=0.8,
        uncertainty_samples=200,
        level_shift_start=level_shift_start,
        absence_windows=absence_windows,
    )


def test_clipping_applies_to_interval_bounds_not_only_the_point_forecast() -> None:
    np.random.seed(0)
    # niedrige Grundlast mit gelegentlichen Spitzen -> Prophet erzeugt reale negative untere Intervallgrenzen, obwohl Verbrauch physikalisch nie negativ sein kann
    history = _history([0.1, 0.1, 5.0, 0.1, 0.1, 0.1] * 10)
    model = _fit(history)
    target_index = pd.date_range(
        history.index[-1] + pd.Timedelta(hours=1), periods=6, freq="1h", tz="UTC"
    )

    unclipped = build_prophet_forecast(
        model,
        target_index,
        clip_negative_forecasts=False,
        history_end=history.index[-1],
        local_timezone="UTC",
        log_transform=False,
    )
    clipped = build_prophet_forecast(
        model,
        target_index,
        clip_negative_forecasts=True,
        history_end=history.index[-1],
        local_timezone="UTC",
        log_transform=False,
    )

    # Voraussetzung für einen aussagekräftigen Test: es müssen überhaupt negative Rohwerte auftreten, sonst würde das Clipping nichts prüfen
    assert (unclipped["y_lower"] < 0).any()

    assert (clipped["y_pred"] >= 0).all()
    assert (clipped["y_lower"] >= 0).all()
    assert (clipped["y_upper"] >= 0).all()


def test_country_holidays_are_added_to_the_model_when_configured() -> None:
    history = _history([0.1, 0.1, 5.0, 0.1, 0.1, 0.1] * 10)

    without_holidays = _fit(history, country_holidays=None)
    with_holidays = _fit(history, country_holidays="UK")

    assert without_holidays.train_holiday_names is None
    assert with_holidays.train_holiday_names is not None
    assert len(with_holidays.train_holiday_names) > 0


def test_forecast_rejects_history_at_or_after_the_forecast_origin() -> None:
    history = _history([1.0, 2.0, 3.0, 4.0])
    model = _fit(history)
    # Zielzeitpunkt liegt nicht nach dem Ende der Trainingshistorie -> Kausalitätsverletzung
    overlapping_target = pd.date_range(
        history.index[-1], periods=1, freq="1h", tz="UTC"
    )

    with pytest.raises(ValueError, match="at or after the forecast origin"):
        build_prophet_forecast(
            model,
            overlapping_target,
            clip_negative_forecasts=False,
            history_end=history.index[-1],
            local_timezone="UTC",
            log_transform=False,
        )


def test_ds_uses_local_time_so_dst_does_not_shift_the_daily_pattern() -> None:
    # 12:00 UTC an einem Sommer- und einem Wintertag -> in London 13:00 BST bzw. 12:00 GMT.
    # Mit UTC als ds-Zeitzone wäre "dieselbe" Stunde an beiden Tagen künstlich verschieden.
    history = pd.Series(
        [1.0, 2.0],
        index=pd.DatetimeIndex(
            ["2020-06-15 12:00:00+00:00", "2020-12-15 12:00:00+00:00"], tz="UTC"
        ),
    )

    prepared = _prepare_prophet_data(history, "Europe/London", log_transform=False)

    assert prepared["ds"].iloc[0].hour == 13
    assert prepared["ds"].iloc[1].hour == 12


def test_log_transform_rejects_non_positive_history() -> None:
    history = _history([1.0, 0.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="strictly positive"):
        _prepare_prophet_data(history, "UTC", log_transform=True)


def test_log_transform_forecast_stays_positive_and_matches_scale() -> None:
    np.random.seed(0)
    # log-normal-artige Werte um 100 mit gelegentlichen Spitzen -> realistischer als reine Konstante
    history = _history([100.0, 90.0, 400.0, 95.0, 105.0, 98.0] * 10)
    model = _fit(history, log_transform=True)
    target_index = pd.date_range(
        history.index[-1] + pd.Timedelta(hours=1), periods=6, freq="1h", tz="UTC"
    )

    forecast = build_prophet_forecast(
        model,
        target_index,
        clip_negative_forecasts=False,
        history_end=history.index[-1],
        local_timezone="UTC",
        log_transform=True,
    )

    # exp() ist nie negativ -> das bekannte negative-Intervallgrenzen-Problem entfällt strukturell
    assert (forecast["y_lower"] >= 0).all()
    # Rücktransformation muss in der Größenordnung der Eingabewerte liegen, nicht im Log-Raum stecken bleiben
    assert forecast["y_pred"].between(10, 1000).all()


def test_level_shift_regressor_is_dropped_once_its_start_left_the_window() -> None:
    history = _history([100.0] * 48)

    inside = _fit(history, level_shift_start=history.index[24])
    before = _fit(history, level_shift_start=history.index[0])

    assert "level_shift" in inside.extra_regressors
    assert "level_shift" not in before.extra_regressors


def test_level_shift_forecast_continues_at_the_new_level() -> None:
    np.random.seed(0)
    history = _history([100.0] * 48 + [200.0] * 24)
    model = _fit(history, level_shift_start=history.index[48])
    target_index = pd.date_range(
        history.index[-1] + pd.Timedelta(hours=1), periods=6, freq="1h", tz="UTC"
    )

    forecast = build_prophet_forecast(
        model,
        target_index,
        clip_negative_forecasts=False,
        history_end=history.index[-1],
        local_timezone="UTC",
        log_transform=False,
    )

    assert forecast["y_pred"].between(180, 220).all()


def test_absence_holidays_cover_the_local_days_of_the_window() -> None:
    # 14.–27.09. in Sommerzeit, lokale Mitternacht ist 23:00 UTC am Vortag
    window = (
        pd.Timestamp("2013-09-13 23:00", tz="UTC"),
        pd.Timestamp("2013-09-27 23:00", tz="UTC"),
    )

    holidays = absence_holidays((window,), "Europe/London")

    assert holidays is not None
    assert (holidays["holiday"] == "absence").all()
    assert holidays["ds"].iloc[0] == pd.Timestamp("2013-09-14")
    assert holidays["ds"].iloc[-1] == pd.Timestamp("2013-09-27")
    assert len(holidays) == 14
    assert absence_holidays((), "Europe/London") is None


def test_forecast_after_an_absence_returns_to_the_normal_level() -> None:
    np.random.seed(0)
    history = _history([100.0] * 24 * 10 + [20.0] * 24 * 7)
    absence = ((history.index[24 * 10], history.index[-1] + pd.Timedelta(hours=1)),)
    target_index = pd.date_range(
        history.index[-1] + pd.Timedelta(hours=1), periods=24, freq="1h", tz="UTC"
    )

    forecasts = {
        label: build_prophet_forecast(
            _fit(history, absence_windows=windows),
            target_index,
            clip_negative_forecasts=False,
            history_end=history.index[-1],
            local_timezone="UTC",
            log_transform=False,
        )
        for label, windows in (("with", absence), ("without", ()))
    }

    assert forecasts["with"]["y_pred"].between(80, 120).all()
    assert forecasts["with"]["y_pred"].mean() > forecasts["without"]["y_pred"].mean()


def test_first_call_always_refits_regardless_of_history_mode() -> None:
    assert is_refit_required(
        False,
        history_mode="fixed_train",
        fitted_at=None,
        current_time=pd.Timestamp("2020-01-02", tz="UTC"),
        retraining_interval_days=1,
        local_timezone="UTC",
    )
    assert is_refit_required(
        False,
        history_mode="expanding",
        fitted_at=None,
        current_time=pd.Timestamp("2020-01-02", tz="UTC"),
        retraining_interval_days=1,
        local_timezone="UTC",
    )


def test_fixed_train_never_refits_again_once_a_model_exists() -> None:
    assert not is_refit_required(
        True,
        history_mode="fixed_train",
        fitted_at=pd.Timestamp("2020-01-01", tz="UTC"),
        current_time=pd.Timestamp("2021-01-01", tz="UTC"),
        retraining_interval_days=None,
        local_timezone="UTC",
    )


def test_expanding_refits_only_once_the_interval_has_elapsed() -> None:
    fitted_at = pd.Timestamp("2020-01-01T00:00:00", tz="UTC")

    assert not is_refit_required(
        True,
        history_mode="expanding",
        fitted_at=fitted_at,
        current_time=fitted_at + pd.Timedelta(hours=23),
        retraining_interval_days=1,
        local_timezone="UTC",
    )
    assert is_refit_required(
        True,
        history_mode="expanding",
        fitted_at=fitted_at,
        current_time=fitted_at + pd.Timedelta(hours=24),
        retraining_interval_days=1,
        local_timezone="UTC",
    )


def test_expanding_without_a_retraining_interval_raises() -> None:
    with pytest.raises(RuntimeError, match="retraining_interval_days"):
        is_refit_required(
            True,
            history_mode="expanding",
            fitted_at=pd.Timestamp("2020-01-01", tz="UTC"),
            current_time=pd.Timestamp("2020-01-02", tz="UTC"),
            retraining_interval_days=None,
            local_timezone="UTC",
        )
