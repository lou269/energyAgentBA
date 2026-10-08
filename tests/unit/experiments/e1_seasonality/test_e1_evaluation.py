import pandas as pd

from experiments.common.evaluation import SCALE_SUSTAINED_COLUMNS
from experiments.e1_seasonality.e1_evaluation import summarize_drift_response
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"


def _run(
    kind: str,
    gate_open: list[bool],
    classifications: list[str],
    alarm: list[bool] | None = None,
    sustained: str | None = None,
) -> pd.DataFrame:
    # Tag -1 bis 4, der 15.04. ist Tag 0
    decision_times = local_calendar_range(
        local_midnight_utc("2014-04-14", TIMEZONE),
        1,
        local_midnight_utc("2014-04-19", TIMEZONE),
        TIMEZONE,
    )
    days = pd.DataFrame(
        {
            "config": "SYS1",
            "kind": kind,
            "cutover_date": "2014-04-15",
            "decision_time": [time.isoformat() for time in decision_times],
            "alarm": alarm if alarm is not None else [False] * 6,
            "gate_open": gate_open,
            "new_pattern": [value == "new_pattern" for value in classifications],
            "dominant_scale": "daily",
        }
    )
    for column in SCALE_SUSTAINED_COLUMNS:
        days[column] = column == sustained and bool(days["gate_open"].any())

    return days


def test_response_counts_only_what_the_control_run_did_not_see() -> None:
    normal = ["normal"] * 6
    runs = [
        _run("control", [False, False, True, False, False, False], normal),
        _run(
            "ramp_28",
            [False, False, True, True, True, False],
            ["normal", "normal", "normal", "new_pattern", "normal", "normal"],
            sustained="weekly_sustained",
        ),
        # Gate nur dort offen, wo es auch ohne Rampe offen ist, und nie new_pattern
        _run("ramp_56", [False, False, True, False, False, False], normal),
        _run(
            "peak",
            [False, False, False, True, False, False],
            normal,
            alarm=[False, False, False, True, False, False],
        ),
    ]

    response = summarize_drift_response(
        pd.concat(runs, ignore_index=True)
    ).response.set_index("kind")

    assert response.loc["ramp_28", "first_event_new_pattern_day"] == 2
    assert response.loc["ramp_28", "first_gate_day"] == 2
    assert response.loc["ramp_28", "gate_open_days"] == 2
    assert response.loc["ramp_28", "trigger_scale"] == "weekly"
    assert pd.isna(response.loc["ramp_56", "first_event_new_pattern_day"])
    assert pd.isna(response.loc["ramp_56", "first_gate_day"])
    assert response.loc["ramp_56", "gate_open_days"] == 0
    assert response.loc["ramp_56", "expected"] == "normal"
    # eine Spitze zeigt sich über die dominante Skala des Alarms
    assert response.loc["peak", "first_gate_day"] == 2
    assert response.loc["peak", "trigger_scale"] == "daily"
    assert response.loc["peak", "expected"] == "peak"
    # das Gate ist im Kontrolllauf an Tag 1 offen, das steht in jeder Zeile
    assert (response["control_gate_open_days"] == 1).all()
