import pandas as pd
import pytest

from experiments.k3_detection.k3_evaluation import (
    add_days_since_cutover,
    pair_with_control,
    summarize_closed_loop,
    summarize_event_response,
)


def _results(kind: str, scores: list[float], classifications: list[str], *, mode: str = "isolated") -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "mode": mode,
            "kind": kind,
            "cutover_date": "2014-04-15",
            "variant": "REF_ROLL60",
            "days_since_cutover": list(range(-1, len(scores) - 1)),
            "anomaly_score": scores,
            "daily_score": scores,
            "weekday_score": scores,
            "weekly_score": scores,
            "long_term_score": [float("nan")] * len(scores),
            "classification": classifications,
            "mae_w": 100.0,
        }
    )
    frame["alarm"] = frame["anomaly_score"].ge(2.0)
    frame["gate_open"] = frame["alarm"]
    frame["new_pattern"] = frame["classification"].eq("new_pattern")
    frame["reference_reset"] = frame["new_pattern"] & frame["mode"].eq("adaption")
    return frame


def test_event_response_only_counts_what_the_control_run_did_not_see() -> None:
    control = _results("control", [0.5, 2.5, 0.5, 2.5, 0.5, 0.5], ["normal", "peak", "normal", "peak", "normal", "normal"])
    # Tag 2 ist auch im Kontrolllauf ein Alarm -> kein Ereignis-Alarm, erster echter Ereignis-Alarm ist Tag 3
    step = _results("step", [0.5, 2.5, 1.0, 3.0, 3.0, 1.0], ["normal", "peak", "normal", "peak", "new_pattern", "normal"])

    paired = pair_with_control(pd.concat([control, step], ignore_index=True))
    response = summarize_event_response(paired, unusual_threshold=2.0).iloc[0]

    assert response["days_after_cutover"] == 4
    assert response["excess_alarm_rate"] == pytest.approx(2 / 4 - 1 / 4)
    assert response["first_event_alarm_day"] == 3
    assert response["first_event_new_pattern_day"] == 3
    assert response["peak_score_shift"] == pytest.approx(2.5)
    assert response["last_day_shift_above_threshold"] == 3


def test_closed_loop_counts_resets_and_compares_mae_with_the_isolated_run() -> None:
    classifications = ["normal", "new_pattern", "normal", "normal", "new_pattern", "normal"]
    runs = [
        _results("control", [0.5] * 6, ["normal", "new_pattern", "normal", "normal", "normal", "normal"], mode="adaption"),
        _results("step", [0.5] * 6, classifications, mode="adaption"),
        _results("control", [0.5] * 6, ["normal"] * 6),
        _results("step", [0.5] * 6, ["normal"] * 6),
    ]
    runs[1]["mae_w"] = 80.0

    summary = summarize_closed_loop(pd.concat(runs, ignore_index=True)).iloc[0]

    # der Reset an Tag 0 ordnet noch den Tag vor dem Cutover ein und zählt im step-Lauf nicht als Treffer
    assert summary["control_resets"] == 1
    assert summary["step_resets_after_cutover"] == 1
    assert summary["step_first_reset_day"] == 3
    assert summary["step_mae_isolated_w"] == pytest.approx(100.0)
    assert summary["step_mae_adaption_w"] == pytest.approx(80.0)


def test_days_since_cutover_count_the_decision_day() -> None:
    results = pd.DataFrame(
        {
            # Mitternacht Ortszeit, der 15.04. ist schon Sommerzeit
            "decision_time": ["2014-04-14T23:00:00+00:00", "2014-04-15T23:00:00+00:00"],
            "cutover_date": "2014-04-15",
        }
    )

    assert list(add_days_since_cutover(results)["days_since_cutover"]) == [0, 1]
