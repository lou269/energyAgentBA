# python -m pytest tests/unit/forecasting/test_walk_forward.py -v

import pandas as pd

from src.config.config_forecasting import ProphetVariantConfig
from src.forecasting.walk_forward import build_walk_forward_forecasts


def _hourly(
    start,
    values: list[float]
) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)


def _no_imputation(
    index: pd.Index
) -> pd.Series:
    return pd.Series(False, index=index)


def test_only_complete_horizons_are_forecasted() -> None:
    fixed_history = _hourly("2019-12-31T22:00", [100.0, 100.0])
    # 30 volle Zielstunden, aber horizon=1 -> die letzten 6 Stunden können keinen
    # vollständigen Horizont mehr bilden und dürfen nicht im Output landen
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), [float(h) for h in range(30)])
    mask = _no_imputation(evaluation_targets.index)

    forecasts = build_walk_forward_forecasts(
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_days=1,
        forecast_origin_step_days=1,
        frequency="1h",
        baseline_model_id="B1",
        growth="linear",
        daily_seasonality=True,
        country_holidays=None,
        local_timezone="UTC",
        log_transform=False,
        interval_width=0.8,
        clip_negative_forecasts=False,
        uncertainty_samples=100,
        config_version="test",
    )

    assert forecasts["forecast_origin"].nunique() == 1
    assert forecasts["target_timestamp"].max() == evaluation_targets.index[23]


def test_available_history_is_strictly_causal_and_grows_between_origins() -> None:
    fixed_history = _hourly("2019-12-31T22:00", [100.0, 100.0])
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), [100.0] * 48)
    mask = _no_imputation(evaluation_targets.index)

    forecasts = build_walk_forward_forecasts(
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_days=1,
        forecast_origin_step_days=1,
        frequency="1h",
        baseline_model_id="B1",
        growth="linear",
        daily_seasonality=True,
        country_holidays=None,
        local_timezone="UTC",
        log_transform=False,
        interval_width=0.8,
        clip_negative_forecasts=False,
        uncertainty_samples=100,
        config_version="test",
    )

    origins = sorted(forecasts["forecast_origin"].unique())
    assert len(origins) == 2

    for origin in origins:
        origin_rows = forecasts.loc[forecasts["forecast_origin"] == origin]
        # Historie darf den Prognoseursprung selbst nie enthalten (Kausalität)
        assert (origin_rows["history_end"] < origin).all()

    first_rows = forecasts.loc[forecasts["forecast_origin"] == origins[0]]
    second_rows = forecasts.loc[forecasts["forecast_origin"] == origins[1]]
    hours_first = first_rows["history_hours"].iloc[0]
    hours_second = second_rows["history_hours"].iloc[0]
    # der gestrige Zielzeitraum wird heute selbst zur Historie -> +24h Wachstum
    assert hours_second - hours_first == 24


def test_forecast_origins_stay_on_local_midnight_across_a_dst_transition() -> None:
    # 2020-03-29: Europe/London stellt die Uhr um 01:00 auf 02:00 vor, feste 24h-Schritte würden
    # den Ursprung an diesem Tag auf 01:00 lokal verschieben statt auf Mitternacht zu bleiben
    fixed_history = _hourly("2020-03-19T23:00:00Z", [100.0])
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), [100.0] * (24 * 12))
    mask = _no_imputation(evaluation_targets.index)

    forecasts = build_walk_forward_forecasts(
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_days=1,
        forecast_origin_step_days=1,
        frequency="1h",
        baseline_model_id="B1",
        growth="linear",
        daily_seasonality=True,
        country_holidays=None,
        local_timezone="Europe/London",
        log_transform=False,
        interval_width=0.8,
        clip_negative_forecasts=False,
        uncertainty_samples=100,
        config_version="test",
    )

    origins = pd.DatetimeIndex(sorted(forecasts["forecast_origin"].unique())).tz_convert("Europe/London")
    assert (origins.hour == 0).all()
    assert len(origins) > 10


def test_prophet_expanding_history_grows_and_retrains_on_schedule() -> None:
    fixed_history = _hourly("2020-01-01", [float(h % 24) for h in range(72)])
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), [float(h % 24) for h in range(48)])
    mask = _no_imputation(evaluation_targets.index)

    variant = ProphetVariantConfig(
        model_id="C2test",
        history_mode="expanding",
        rolling_window_days=None,
        retraining_interval_days=1,
    )

    forecasts = build_walk_forward_forecasts(
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_days=1,
        forecast_origin_step_days=1,
        frequency="1h",
        prophet_variant=variant,
        growth="linear",
        daily_seasonality=False,
        country_holidays=None,
        local_timezone="UTC",
        log_transform=False,
        interval_width=0.8,
        clip_negative_forecasts=False,
        uncertainty_samples=20,
        config_version="test",
    )

    origins = sorted(forecasts["forecast_origin"].unique())
    assert len(origins) == 2

    first_rows = forecasts.loc[forecasts["forecast_origin"] == origins[0]]
    second_rows = forecasts.loc[forecasts["forecast_origin"] == origins[1]]

    # das erste Training zählt nicht als "Retraining", nur das planmäßige zweite
    assert not first_rows["retrained"].iloc[0]
    assert second_rows["retrained"].iloc[0]
    # Historie wächst um genau die seit dem letzten Ursprung vergangenen 24h
    assert second_rows["history_hours"].iloc[0] - first_rows["history_hours"].iloc[0] == 24


def test_prophet_fixed_train_reuses_the_same_model_and_history() -> None:
    fixed_history = _hourly("2020-01-01", [float(h % 24) for h in range(72)])
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), [float(h % 24) for h in range(48)])
    mask = _no_imputation(evaluation_targets.index)

    variant = ProphetVariantConfig(
        model_id="C1test",
        history_mode="fixed_train",
        rolling_window_days=None,
        retraining_interval_days=None,
    )

    forecasts = build_walk_forward_forecasts(
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_days=1,
        forecast_origin_step_days=1,
        frequency="1h",
        prophet_variant=variant,
        growth="linear",
        daily_seasonality=False,
        country_holidays=None,
        local_timezone="UTC",
        log_transform=False,
        interval_width=0.8,
        clip_negative_forecasts=False,
        uncertainty_samples=20,
        config_version="test",
    )

    assert forecasts["forecast_origin"].nunique() == 2
    # fixed_train nutzt bei jedem Ursprung exakt dieselbe Historie, nie die inzwischen verfügbaren neueren Daten
    assert forecasts["history_hours"].nunique() == 1
    assert forecasts["history_start"].nunique() == 1
    assert forecasts["history_end"].nunique() == 1
    assert not forecasts["retrained"].any()