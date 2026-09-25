import numpy as np
import pandas as pd

from experiments.k4_llm.k4_evaluation import summarize_sequence
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"


def _run(
    kind: str,
    gate_open: list[bool],
    classifications: list[str],
    resets: list[bool] | None = None,
    errors: list[str | None] | None = None,
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
            "kind": kind,
            "cutover_date": "2014-04-15",
            "config": "MDL0",
            "decision_time": [time.isoformat() for time in decision_times],
            "classification": classifications,
            "alarm": gate_open,
            "gate_open": gate_open,
            "new_pattern": [value == "new_pattern" for value in classifications],
            "reference_reset": resets or [False] * 6,
            "error": errors or [np.nan] * 6,
        }
    )


def test_sequence_counts_the_expected_class_only_on_days_the_event_opened_the_gate() -> (
    None
):
    normal = ["normal"] * 6
    runs = [
        _run(
            "control",
            [False, False, False, False, True, False],
            ["normal", "normal", "normal", "normal", "low", "normal"],
        ),
        _run(
            "step",
            [False, False, True, True, True, False],
            ["normal", "normal", "peak", "new_pattern", "new_pattern", "normal"],
            resets=[False, False, False, True, False, False],
            errors=[None, None, None, None, None, "timeout"],
        ),
        _run(
            "peak_6",
            [False, False, True, False, False, False],
            ["normal", "normal", "peak", "normal", "normal", "normal"],
        ),
        # Gate nur dort offen, wo es auch im Kontrolllauf offen ist
        _run("ramp_56", [False, False, False, False, True, False], normal),
    ]

    summary = summarize_sequence(pd.concat(runs, ignore_index=True))
    events = summary.events.set_index("kind")
    models = summary.models.set_index("config")

    assert events.loc["step", "expected_classification"] == "new_pattern"
    # Tag 3 zählt nicht, dort ist das Gate auch ohne Stufe offen
    assert events.loc["step", "correct_days"] == 1
    assert events.loc["step", "first_correct_day"] == 2
    assert events.loc["step", "resets"] == 1
    assert events.loc["peak_6", "first_correct_day"] == 1
    assert pd.isna(events.loc["ramp_56", "first_correct_day"])

    assert models.loc["MDL0", "detected_kinds"] == 2
    assert models.loc["MDL0", "event_kinds"] == 3
    assert models.loc["MDL0", "control_notification_days"] == 1
    assert models.loc["MDL0", "failed_days"] == 1
