import pandas as pd

from experiments.e3_saisonality.e3_evaluation import summarize_drift_response
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"


def _run(
    config: str,
    kind: str,
    gate_open: list[bool],
    classifications: list[str],
    day_error_w: float = 100.0,
) -> pd.DataFrame:
    # Tag -1 bis 4, der 15.04. ist Tag 0
    decision_times = local_calendar_range(
        local_midnight_utc("2014-04-14", TIMEZONE),
        1,
        local_midnight_utc("2014-04-19", TIMEZONE),
        TIMEZONE,
    )
    return pd.DataFrame(
        {
            "config": config,
            "kind": kind,
            "cutover_date": "2014-04-15",
            "decision_time": [time.isoformat() for time in decision_times],
            "alarm": gate_open,
            "gate_open": gate_open,
            "new_pattern": [value == "new_pattern" for value in classifications],
            # die Regel setzt bei new_pattern zurück
            "adaption_action": [
                "advance_history_start" if value == "new_pattern" else "none"
                for value in classifications
            ],
            "day_error_w": day_error_w,
            "mae_w": day_error_w,
            "mape_pct": 10.0,
        }
    )


def test_drift_response_counts_only_what_the_control_run_did_not_see() -> None:
    normal = ["normal"] * 6
    runs = [
        _run("SYS1", "control", [False] * 6, normal),
        _run("SYS1", "ramp_28", [False] * 6, normal),
        _run("SYS1", "ramp_56", [False] * 6, normal),
        _run("SYS2", "control", [False, False, True, False, False, False], normal),
        _run(
            "SYS2",
            "ramp_28",
            [False, False, True, True, True, False],
            ["normal", "normal", "normal", "new_pattern", "normal", "normal"],
            day_error_w=90.0,
        ),
        # Gate nur dort offen, wo es auch ohne Rampe offen ist, und nie new_pattern
        _run("SYS2", "ramp_56", [False, False, True, False, False, False], normal),
        # SYS3 hat schon im Kontrolllauf an Tag 2 ein new_pattern, das zählt nicht gegen SYS2
        _run(
            "SYS3",
            "control",
            [False, False, True, True, False, False],
            ["normal", "normal", "normal", "new_pattern", "normal", "normal"],
        ),
        _run(
            "SYS3",
            "ramp_28",
            [False, False, True, True, True, False],
            ["normal", "normal", "normal", "new_pattern", "new_pattern", "normal"],
        ),
        _run("SYS3", "ramp_56", [False] * 6, normal),
    ]

    response = summarize_drift_response(
        pd.concat(runs, ignore_index=True), "SYS1"
    ).response.set_index(["config", "kind"])

    assert "SYS1" not in response.index.get_level_values("config")
    assert response.loc[("SYS2", "ramp_28"), "first_event_new_pattern_day"] == 2
    assert response.loc[("SYS2", "ramp_28"), "gate_open_days"] == 2
    assert pd.isna(response.loc[("SYS2", "ramp_56"), "first_event_new_pattern_day"])
    assert response.loc[("SYS2", "ramp_56"), "gate_open_days"] == 0
    assert response.loc[("SYS2", "ramp_56"), "expected"] == "normal"
    assert response.loc[("SYS3", "ramp_28"), "first_event_new_pattern_day"] == 3
    assert response.loc[("SYS3", "ramp_28"), "gate_open_days"] == 1
    # ab dem Reset an Tag 2 gegen SYS1 am selben Tag
    assert response.loc[("SYS2", "ramp_28"), "reset_forecast_day"] == 2
    assert response.loc[("SYS2", "ramp_28"), "mean_delta"] == -10
    # der Reset im Kontrolllauf von SYS3 ist ein falscher und steht in der control-Zeile
    assert response.loc[("SYS3", "control"), "reset_forecast_day"] == 2
    assert pd.isna(response.loc[("SYS2", "control"), "reset_forecast_day"])
