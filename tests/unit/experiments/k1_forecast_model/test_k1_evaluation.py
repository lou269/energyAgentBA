import pandas as pd
import pytest

from experiments.k1_forecast_model.k1_evaluation import (
    WHOLE_YEAR,
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
