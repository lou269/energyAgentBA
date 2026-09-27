import pandas as pd

from experiments.e3_saisonality.e3_evaluation import summarize_ramp_response
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"


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
