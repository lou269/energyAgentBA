# python -m pytest tests/unit/forecasting/test_forecasting.py -v

import pandas as pd

from src.forecasting.forecasting import run_forecast_comparison
from src.forecasting.walk_forward import ProphetVariantParameters


def _hourly(start, values: list[float]) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)



def test_combines_baselines_and_a_prophet_variant_into_one_evaluated_comparison() -> None:
    fixed_history = _hourly("2020-01-01", [float(h % 24) for h in range(72)])
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), [float(h % 24) for h in range(48)])
    mask = pd.Series(False, index=evaluation_targets.index)

    variant: ProphetVariantParameters = {
        "model_id": "C2test",
        "history_mode": "expanding",
        "rolling_window_hours": None,
        "retraining_interval_hours": 24,
        "weekly_seasonality": False,
        "yearly_seasonality": False,
    }

    forecasts, evaluation_results = run_forecast_comparison(
        ("B1", variant),
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_hours=24,
        forecast_origin_step_hours=24,
        frequency="1h",
        local_timezone="UTC",
        clip_negative_forecasts=False,
        config_version="test",
        growth="linear",
        daily_seasonality=False,
        country_holidays=None,
        log_transform=False,
        interval_width=0.8,
        uncertainty_samples=20,
        comparison_model_ids=("C2test",),
        reference_model_ids=("B1",),
        nominal_interval_level=0.8,
        mape_min_eligible_watts=10.0,
    )
    
    
    assert set(forecasts["model_id"].unique()) == {"B1", "C2test"}
    assert set(evaluation_results["overall_metrics"]["model_id"]) == {"B1", "C2test"}
    assert evaluation_results["mae_skill"]["reference_model_id"].eq("B1").all()