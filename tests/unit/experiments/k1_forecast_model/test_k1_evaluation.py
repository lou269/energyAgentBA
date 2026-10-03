import pandas as pd
import pytest

from experiments.k1_forecast_model.k1_evaluation import (
    WHOLE_YEAR,
    summarize_daily_error,
    summarize_seasonal_forecast,
)


def test_seasonal_forecast_averages_each_month_and_pairs_the_same_days() -> None:
    days = ["2014-04-29", "2014-04-30", "2014-05-01"]
    origin_metrics = pd.DataFrame(
        {
            "model_id": ["C2"] * 3 + ["S1"] * 3,
            "forecast_origin": days * 2,
            "forecast_day": days * 2,
            "mae_w": [100.0, 120.0, 90.0, 90.0, 100.0, 90.0],
        }
    )

    summary = summarize_seasonal_forecast(origin_metrics, (("S1", "C2"),))
    by_month = summary.by_month.set_index("month")

    assert by_month.loc["2014-04", "C2"] == 110.0
    assert by_month.loc[WHOLE_YEAR, "S1"] == pytest.approx(280 / 3)
    assert summary.paired.loc[0, "mean_delta"] == pytest.approx(-10.0)
    assert summary.paired.loc[0, "reference"] == "C2"


def test_daily_energy_error_uses_the_day_mean_and_skips_incomplete_days() -> None:
    d1 = pd.Timestamp("2014-05-01 22:00", tz="UTC")
    d2 = pd.Timestamp("2014-05-02 22:00", tz="UTC")
    # Tag 1: Stundenfehler +100/-100 heben sich im Tagesmittel auf, Tag 2 hat eine nicht bewertete Stunde
    forecasts = pd.DataFrame(
        {
            "model_id": ["B2"] * 4,
            "forecast_origin": [d1, d1, d2, d2],
            "y_pred": [600.0, 400.0, 500.0, 500.0],
            "target_eligible": [True, True, True, False],
        }
    )
    actual = pd.Series([500.0, 400.0], index=[d1, d2])

    daily = summarize_daily_error(forecasts, actual)

    assert daily.loc["B2", "daily_count"] == 1
    assert daily.loc["B2", "daily_mae_w"] == 0.0
