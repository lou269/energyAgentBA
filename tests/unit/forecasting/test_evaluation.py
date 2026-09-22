# python -m pytest tests/unit/forecasting/test_evaluation.py -v

import pandas as pd
import pytest

from src.forecasting.evaluation import evaluate_forecasts, select_primary_naive_reference
from src.forecasting.walk_forward import build_walk_forward_forecasts


def _hourly(
    start, 
    values: list[float]
) -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="1h", tz="UTC")
    return pd.Series(values, index=index)


def _b1_forecasts(
    y_true: list[float]
) -> pd.DataFrame:
    fixed_history = _hourly("2020-01-01", [100.0, 100.0])
    evaluation_targets = _hourly(fixed_history.index[-1] + pd.Timedelta(hours=1), y_true)
    mask = pd.Series(False, index=evaluation_targets.index)

    return build_walk_forward_forecasts(
        fixed_history,
        evaluation_targets,
        mask,
        run_id="r1",
        experiment_id="e1",
        split="validation",
        horizon_hours=len(y_true),
        forecast_origin_step_hours=len(y_true),
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


def test_mae_and_rmse_match_hand_calculated_errors() -> None:
    # B1 sagt konstant 100.0 W voraus (letzter Historienwert) -> Fehler sind direkt nachrechenbar
    forecasts = _b1_forecasts([100.0, 5.0, 100.0])

    results = evaluate_forecasts(
        forecasts,
        horizon_hours=3,
        comparison_model_ids=("B1",),
        reference_model_ids=("B1",),
        nominal_interval_level=0.8,
        mape_min_eligible_watts=0.0,
    )

    overall = results["overall_metrics"].iloc[0]
    # Fehler pro Stunde: 0, 95, 0 -> MAE=95/3, RMSE=sqrt(95^2/3)
    assert overall["mae_w"] == pytest.approx(95.0 / 3.0)
    assert overall["rmse_w"] == pytest.approx((95.0**2 / 3.0) ** 0.5)


def test_mape_floor_excludes_near_zero_reference_from_mape() -> None:
    # derselbe Fehler wie oben, aber die Auswirkung auf MAPE steht im Fokus: der 5.0-W-Zielwert
    # liegt so nah an 0, dass sein Fehleranteil den Durchschnitt dominiert
    forecasts = _b1_forecasts([100.0, 5.0, 100.0])

    without_floor = evaluate_forecasts(
        forecasts,
        horizon_hours=3,
        comparison_model_ids=("B1",),
        reference_model_ids=("B1",),
        nominal_interval_level=0.8,
        mape_min_eligible_watts=0.0,
    )["overall_metrics"].iloc[0]

    with_floor = evaluate_forecasts(
        forecasts,
        horizon_hours=3,
        comparison_model_ids=("B1",),
        reference_model_ids=("B1",),
        nominal_interval_level=0.8,
        mape_min_eligible_watts=10.0,
    )["overall_metrics"].iloc[0]

    # ohne Floor: (0% + 1900% + 0%) / 3 - der 5-W-Zeitpunkt dominiert den Durchschnitt
    assert without_floor["mape_pct"] == pytest.approx(1900.0 / 3.0)
    assert without_floor["mape_below_floor_target_count"] == 0

    # mit Floor: der 5-W-Zeitpunkt wird ausgeschlossen, übrig bleiben zwei Nullfehler
    assert with_floor["mape_pct"] == pytest.approx(0.0)
    assert with_floor["mape_target_count"] == 2
    assert with_floor["mape_below_floor_target_count"] == 1


def test_select_primary_naive_reference_picks_lowest_mae() -> None:
    overall_metrics = pd.DataFrame(
        {
            "run_id": ["r1"] * 3,
            "split": ["validation"] * 3,
            "model_id": ["B1", "B2", "B3"],
            "mae_w": [50.0, 20.0, 30.0],
            "rmse_w": [60.0, 25.0, 35.0],
        }
    )

    assert select_primary_naive_reference(overall_metrics, ("B1", "B2", "B3")) == "B2"


def test_select_primary_naive_reference_raises_without_evaluable_targets() -> None:
    overall_metrics = pd.DataFrame(
        {
            "run_id": ["r1"] * 2,
            "split": ["validation"] * 2,
            "model_id": ["B1", "B2"],
            "mae_w": [float("nan"), float("nan")],
            "rmse_w": [float("nan"), float("nan")],
        }
    )

    with pytest.raises(ValueError, match="without evaluable targets"):
        select_primary_naive_reference(overall_metrics, ("B1", "B2"))