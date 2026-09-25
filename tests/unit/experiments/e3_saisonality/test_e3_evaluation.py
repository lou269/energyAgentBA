import pandas as pd
import pytest

from experiments.e3_saisonality.e3_evaluation import (
    WHOLE_YEAR,
    summarize_ramp_response,
    summarize_seasonal_forecast,
)
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"


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


def _run(kind: str, gate_open: list[bool], classifications: list[str]) -> pd.DataFrame:
    # Tag -1 bis 4, der 15.04. ist Tag 0
    decision_times = local_calendar_range(
        local_midnight_utc("2014-04-14", TIMEZONE),
        1,
        local_midnight_utc("2014-04-19", TIMEZONE),
        TIMEZONE,
    )
    return pd.DataFrame(
        {
            "kind": kind,
            "cutover_date": "2014-04-15",
            "decision_time": [time.isoformat() for time in decision_times],
            "alarm": gate_open,
            "gate_open": gate_open,
            "new_pattern": [value == "new_pattern" for value in classifications],
        }
    )


def test_ramp_response_counts_only_what_the_control_run_did_not_see() -> None:
    normal = ["normal"] * 6
    runs = [
        _run("control", [False, False, True, False, False, False], normal),
        _run(
            "scaled",
            [False, False, True, True, True, False],
            ["normal", "normal", "normal", "new_pattern", "normal", "normal"],
        ),
        # Gate nur dort offen, wo es auch ohne Rampe offen ist, und nie new_pattern
        _run("ramp_56", [False, False, True, False, False, False], normal),
    ]

    summary = summarize_ramp_response(pd.concat(runs, ignore_index=True))
    detection = summary.detection.set_index("kind")
    gate_open = summary.gate_open.set_index("kind")

    assert detection.loc["scaled", "2014-04-15"] == 2
    assert detection.loc["scaled", "detected"] == "1/1"
    assert pd.isna(detection.loc["ramp_56", "2014-04-15"])
    assert detection.loc["ramp_56", "detected"] == "0/1"
    assert gate_open.loc["scaled", "mean"] == 2
    assert gate_open.loc["ramp_56", "mean"] == 0
