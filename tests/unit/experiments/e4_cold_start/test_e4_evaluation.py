import pandas as pd
import pytest

from experiments.common.scenarios import local_day_window, slice_history_window
from experiments.e4_cold_start.e4_evaluation import (
    add_days_since_start,
    build_learning_curve,
    find_break_even_days,
    summarize_windows,
)

TIMEZONE = "Europe/London"


def _origin_metrics(
    start_date: str, coldstart_days: int, model_id: str, mae: list[float]
) -> pd.DataFrame:
    origins = pd.date_range(
        start_date, periods=len(mae), freq="D", tz=TIMEZONE
    ).tz_convert("UTC")
    return pd.DataFrame(
        {
            "start_date": start_date,
            "coldstart_days": coldstart_days,
            "model_id": model_id,
            "forecast_origin": origins,
            "mae_w": mae,
            "mape_pct": [value / 10 for value in mae],
        }
    )


def test_coldstart_window_counts_local_days_across_the_clock_change() -> None:
    index = pd.date_range("2014-03-01", "2014-06-30", freq="1h", tz="UTC")
    series = pd.Series(300.0, index=index)

    start, end = local_day_window("2014-03-31", 14)
    history, targets, _imputed = slice_history_window(
        series,
        pd.Series(False, index=index),
        start=start,
        end=end,
        history_days=7,
    )

    # Umstellung am 30.03.: 7 lokale Tage sind hier nur 167 Stunden
    assert history.index[0] == pd.Timestamp("2014-03-24 00:00", tz="UTC")
    assert len(history) == 167
    assert targets.index[0] == pd.Timestamp("2014-03-30 23:00", tz="UTC")
    assert len(targets) == 14 * 24


def test_break_even_is_the_first_day_the_variant_beats_the_baseline() -> None:
    origin_metrics = pd.concat(
        [
            _origin_metrics("2014-03-28", 7, "C3_30", [200.0, 180.0, 140.0, 130.0]),
            _origin_metrics("2014-03-28", 7, "B2", [150.0, 150.0, 150.0, 150.0]),
            _origin_metrics("2014-07-15", 7, "C3_30", [140.0, 140.0, 140.0, 140.0]),
            _origin_metrics("2014-07-15", 7, "B2", [150.0, 150.0, 150.0, 150.0]),
        ],
        ignore_index=True,
    )

    daily = add_days_since_start(origin_metrics)
    # Starttermin vor der Zeitumstellung, trotzdem ganze Tage
    assert daily["day_since_start"].tolist()[:4] == [0, 1, 2, 3]

    curve = build_learning_curve(daily, smoothing_days=2)
    break_even = find_break_even_days(
        curve, variant_id="C3_30", reference_model_id="B2"
    ).set_index("start_date")

    # geglättet: 200, 190, 160, 135 gegen 150
    assert break_even.at["2014-03-28", "break_even_day"] == 3
    assert break_even.at["2014-07-15", "break_even_day"] == 0
    # alle: 170, 165, 150, 137.5 -> erst Tag 3 liegt echt unter 150
    assert break_even.at["alle", "break_even_day"] == 3


def test_window_summary_reports_skill_and_gap_to_the_longest_coldstart() -> None:
    origin_metrics = pd.concat(
        [
            _origin_metrics("2014-07-15", 7, "C3_30", [160.0, 160.0, 120.0, 120.0]),
            _origin_metrics("2014-07-15", 7, "B2", [200.0, 200.0, 200.0, 200.0]),
            _origin_metrics("2014-07-15", 30, "C3_30", [130.0, 130.0, 120.0, 120.0]),
            _origin_metrics("2014-07-15", 30, "B2", [200.0, 200.0, 200.0, 200.0]),
        ],
        ignore_index=True,
    )

    summary = summarize_windows(
        add_days_since_start(origin_metrics),
        variant_id="C3_30",
        reference_model_id="B2",
        window_edges_days=(2, 4),
    )
    first_window = summary.loc[
        summary["start_date"].eq("2014-07-15") & summary["window"].eq("0-1")
    ].set_index("coldstart_days")

    assert first_window.at[7, "mae_skill"] == pytest.approx(0.2)
    assert first_window.at[7, "mae_gap_to_steady_state_w"] == pytest.approx(30.0)
    assert first_window.at[30, "mae_gap_to_steady_state_w"] == pytest.approx(0.0)
    assert (
        summary.loc[summary["window"].eq("2-3"), "mae_gap_to_steady_state_w"]
        .eq(0.0)
        .all()
    )
