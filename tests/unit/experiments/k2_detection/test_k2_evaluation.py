import pandas as pd

from experiments.common.evaluation import pair_with_control
from experiments.k2_detection.k2_evaluation import PAIR_KEYS, summarize_detection


def _results(
    kind: str,
    alarms: list[bool],
    classifications: list[str],
    *,
    mode: str = "isolated",
    cutover_date: str = "2014-04-15",
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "mode": mode,
            "kind": kind,
            "cutover_date": cutover_date,
            "variant": "REF_ROLL60",
            "days_since_cutover": list(range(-1, len(alarms) - 1)),
            "alarm": alarms,
            "gate_open": alarms,
            "classification": classifications,
            "dominant_scale": "daily",
            "daily_sustained": False,
            "weekday_sustained": False,
            "weekly_sustained": True,
            "long_term_sustained": True,
        }
    )
    frame["new_pattern"] = frame["classification"].eq("new_pattern")
    return frame


def test_detection_peak_day_and_step_reset() -> None:
    normal = ["normal"] * 5
    runs = [
        _results("control", [False] * 5, normal, mode="adaption"),
        _results(
            "step_30",
            [False] * 5,
            ["normal", "normal", "normal", "new_pattern", "normal"],
            mode="adaption",
        ),
        _results("peak", [False, False, True, False, False], normal, mode="adaption"),
        # hier kommt der Alarm erst einen Tag nach dem Ereignistag
        _results(
            "control", [False] * 5, normal, mode="adaption", cutover_date="2014-01-15"
        ),
        _results(
            "peak",
            [False, False, False, True, False],
            normal,
            mode="adaption",
            cutover_date="2014-01-15",
        ),
        _results(
            "step_30", [False] * 5, normal, mode="adaption", cutover_date="2014-01-15"
        ),
    ]

    detection = summarize_detection(
        pair_with_control(pd.concat(runs, ignore_index=True), PAIR_KEYS),
        ("peak",),
        control_reset_tolerance_days=7,
        uncounted_cutovers=(),
    ).table.set_index("kind")

    assert detection.loc["step_30", "detected"] == "1/2"
    assert detection.loc["step_30", "2014-04-15"] == 2
    assert detection.loc["step_30", "scales"] == "weekly+long_term"
    assert detection.loc["peak", "detected"] == "1/2"
    assert detection.loc["peak", "2014-04-15"] == 1
    assert pd.isna(detection.loc["peak", "2014-01-15"])
    assert detection.loc["peak", "scales"] == "daily"


def _reset_on(day: int, days: int = 12) -> list[str]:
    # Tag -1 steht an Position 0
    return [
        "new_pattern" if position - 1 == day else "normal" for position in range(days)
    ]


def test_detection_skips_shifted_and_uncounted() -> None:
    quiet = [False] * 12
    peak_alarm = [False, False, True] + [False] * 9
    runs = [
        _results("control", quiet, _reset_on(10), mode="adaption"),
        # einen Tag vor dem Reset der Kontrolle, also derselbe natürliche Wechsel
        _results("step_30", quiet, _reset_on(9), mode="adaption"),
        _results("peak", peak_alarm, _reset_on(2), mode="adaption"),
        _results(
            "control",
            quiet,
            ["normal"] * 12,
            mode="adaption",
            cutover_date="2013-10-15",
        ),
        _results(
            "step_30", quiet, _reset_on(5), mode="adaption", cutover_date="2013-10-15"
        ),
        _results(
            "peak",
            peak_alarm,
            ["normal"] * 12,
            mode="adaption",
            cutover_date="2013-10-15",
        ),
    ]

    summary = summarize_detection(
        pair_with_control(pd.concat(runs, ignore_index=True), PAIR_KEYS),
        ("peak",),
        control_reset_tolerance_days=7,
        uncounted_cutovers=("2013-10-15",),
    )
    detection = summary.table.set_index("kind")

    assert pd.isna(detection.loc["step_30", "2014-04-15"])
    assert detection.loc["step_30", "2013-10-15"] == 5
    assert detection.loc["step_30", "detected"] == "0/1"
    assert detection.loc["step_30", "false_resets"] == 0
    # die Spitze zählt auch im nicht gezählten Cutover
    assert detection.loc["peak", "detected"] == "2/2"
    assert detection.loc["peak", "false_resets"] == 0.5
    assert summary.false_resets["false_resets"].iloc[0] == 0.25
