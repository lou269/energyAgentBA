import pandas as pd
import pytest

from experiments.k1_forecast_model.k1_evaluation import (
    WHOLE_YEAR,
    score_forecast_days,
    summarize_daily_error,
    summarize_seasonal_forecast,
)


def _flat_forecasts(predictions: dict[str, list[float]], origins: list) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "model_id": [model for model in predictions for _ in origins],
            "forecast_origin": origins * len(predictions),
            "y_pred": [value for values in predictions.values() for value in values],
        }
    )


def test_seasonal_forecast_averages_each_month_and_pairs_the_same_days() -> None:
    origins = list(
        pd.to_datetime(
            ["2014-04-28 23:00", "2014-04-29 23:00", "2014-04-30 23:00"]
        ).tz_localize("UTC")
    )
    actual = pd.Series([500.0, 500.0, 500.0], index=origins)
    forecasts = _flat_forecasts(
        {"C2": [600.0, 620.0, 590.0], "S1": [590.0, 600.0, 590.0]}, origins
    )

    summary = summarize_seasonal_forecast(forecasts, actual, (("S1", "C2"),))
    by_month = summary.by_month.set_index("month")

    assert by_month.loc["2014-04", "C2"] == 110.0
    assert by_month.loc[WHOLE_YEAR, "S1"] == pytest.approx(280 / 3)
    assert summary.paired.loc[0, "mean_delta"] == pytest.approx(-10.0)
    assert summary.paired.loc[0, "reference"] == "C2"


def test_daily_energy_error_uses_the_day_mean_and_skips_days_without_actual() -> None:
    d1 = pd.Timestamp("2014-05-01 22:00", tz="UTC")
    d2 = pd.Timestamp("2014-05-02 22:00", tz="UTC")
    # Tag 1: Stundenfehler +100/-100 heben sich im Tagesmittel auf, Tag 2 hat kein Ist-Tagesmittel
    forecasts = pd.DataFrame(
        {
            "model_id": ["B2"] * 4,
            "forecast_origin": [d1, d1, d2, d2],
            "y_pred": [600.0, 400.0, 500.0, 500.0],
        }
    )
    actual = pd.Series([500.0, float("nan")], index=[d1, d2])

    daily = summarize_daily_error(score_forecast_days(forecasts, actual))

    assert daily.loc["B2", "daily_count"] == 1
    assert daily.loc["B2", "daily_mae_w"] == 0.0
