import pandas as pd

from experiments.e1_seasonality.e1_evaluation import summarize_detection
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"


def _run(
    kind: str,
    alarm: list[bool] | None = None,
    sustained_drift: list[bool] | None = None,
    cutover_date: str = "2014-04-15",
) -> pd.DataFrame:
    # Tag -1 bis 4
    cutover = pd.Timestamp(cutover_date)
    decision_times = local_calendar_range(
        local_midnight_utc(
            (cutover - pd.Timedelta(days=1)).strftime("%Y-%m-%d"), TIMEZONE
        ),
        1,
        local_midnight_utc(
            (cutover + pd.Timedelta(days=4)).strftime("%Y-%m-%d"), TIMEZONE
        ),
        TIMEZONE,
    )
    return pd.DataFrame(
        {
            "config": "SYS1",
            "kind": kind,
            "cutover_date": cutover_date,
            "decision_time": [time.isoformat() for time in decision_times],
            "dominant_scale": "weekday",
            "alarm": alarm or [False] * 6,
            "sustained_drift": sustained_drift or [False] * 6,
        }
    )


def test_event_counts_only_its_own_signal_the_control_run_did_not_have() -> None:
    runs = [
        # Alarm an Tag 1 und Streak an Tag 3 auch ohne Ereignis
        _run(
            "control",
            alarm=[False, False, True, False, False, False],
            sustained_drift=[False, False, False, False, True, False],
        ),
        _run(
            "ramp_28",
            sustained_drift=[False, False, False, True, True, False],
        ),
        # der Streak ist schon in der Kontrolle da, der Alarm zählt für die Rampe nicht
        _run(
            "ramp_56",
            alarm=[False, False, True, True, False, False],
            sustained_drift=[False, False, False, False, True, False],
        ),
        # ein Streak zählt für die Spitze nicht, der Alarm an Tag 1 ist schon in der Kontrolle da
        _run(
            "peak",
            alarm=[False, False, True, False, True, False],
            sustained_drift=[False, False, False, True, False, False],
        ),
    ]

    summary = summarize_detection(pd.concat(runs, ignore_index=True))
    cases = summary.cases.set_index("kind")

    assert cases.loc["ramp_28", "first_event_day"] == 2
    assert pd.isna(cases.loc["ramp_56", "first_event_day"])
    # der Alarm an Tag 3 zählt nicht, eine Spitze gilt nur an Tag 1
    assert pd.isna(cases.loc["peak", "first_event_day"])
    assert pd.isna(cases.loc["ramp_28", "trigger_scale"])
    assert cases.loc["ramp_28", "expected"] == "reset"
    assert cases.loc["ramp_56", "expected"] == "silent"
    assert cases.loc["peak", "control_signal_days"] == 1
    assert cases.loc["ramp_28", "control_signal_days"] == 1


def test_overview_averages_over_detected_cutovers_only() -> None:
    runs = []
    for cutover, drift_days in [
        ("2014-04-15", [2, 4]),
        ("2014-05-15", [3]),
        ("2014-06-15", []),
    ]:
        drift = [index in drift_days for index in range(6)]
        runs += [
            _run("control", cutover_date=cutover),
            _run("scaled", sustained_drift=drift, cutover_date=cutover),
        ]

    overview = summarize_detection(pd.concat(runs, ignore_index=True)).overview.iloc[0]

    assert (overview["cases"], overview["detected"]) == (3, 2)
    assert overview["mean_day"] == 1.5
    assert (overview["first_day"], overview["last_day"]) == (1, 2)


def test_peak_counts_only_on_its_own_day() -> None:
    runs = [
        _run("control"),
        _run("peak", alarm=[False, False, True, False, False, False]),
    ]

    summary = summarize_detection(pd.concat(runs, ignore_index=True))
    case = summary.cases.iloc[0]
    overview = summary.overview.iloc[0]

    assert case["first_event_day"] == 1
    assert case["trigger_scale"] == "weekday"
    assert overview["detected"] == 1
    assert pd.isna(overview["mean_day"])
