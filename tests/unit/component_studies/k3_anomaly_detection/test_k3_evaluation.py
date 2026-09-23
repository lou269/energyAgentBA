import pandas as pd
import pytest

from experiments.component_studies.k3_anomaly_detection.k3_evaluation import pair_with_control, summarize_closed_loop, summarize_event_response
from experiments.component_studies.k3_anomaly_detection.k3_scenarios import build_k3_scenarios


def _results(kind: str, scores: list[float], classifications: list[str], *, mode: str = "isolated") -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "mode": mode,
            "kind": kind,
            "cutover_date": "2014-04-15",
            "variant": "REF_ROLL60",
            "days_since_cutover": list(range(-2, len(scores) - 2)),
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
    frame["new_pattern"] = frame["classification"].eq("new_pattern")
    frame["reference_reset"] = frame["new_pattern"] & frame["mode"].eq("adaption")
    return frame


def test_event_response_only_counts_what_the_control_run_did_not_see() -> None:
    control = _results("control", [0.5, 2.5, 0.5, 2.5, 0.5, 0.5], ["normal", "peak", "normal", "peak", "normal", "normal"])
    # Tag 1 ist auch im Kontrolllauf ein Alarm -> kein Ereignis-Alarm, erster echter Ereignis-Alarm ist Tag 2
    step = _results("step", [0.5, 2.5, 1.0, 3.0, 3.0, 1.0], ["normal", "peak", "normal", "peak", "new_pattern", "normal"])

    paired = pair_with_control(pd.concat([control, step], ignore_index=True))
    response = summarize_event_response(paired, unusual_threshold=2.0).iloc[0]

    assert response["days_after_cutover"] == 4
    assert response["excess_alarm_rate"] == pytest.approx(2 / 4 - 1 / 4)
    assert response["first_event_alarm_day"] == 2
    assert response["first_event_new_pattern_day"] == 2
    assert response["peak_score_shift"] == pytest.approx(2.5)
    assert response["last_day_shift_above_threshold"] == 2


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

    # der Reset vor dem Cutover (Tag -1) zählt im step-Lauf nicht als Treffer
    assert summary["control_resets"] == 1
    assert summary["step_resets_after_cutover"] == 1
    assert summary["step_first_reset_day"] == 2
    assert summary["step_mae_isolated_w"] == pytest.approx(100.0)
    assert summary["step_mae_adaption_w"] == pytest.approx(80.0)


def test_step_scenario_shares_decision_times_and_only_differs_after_the_cutover() -> None:
    index = pd.date_range("2014-01-01", "2014-06-30", freq="1h", tz="UTC")
    mains = pd.Series(300.0, index=index, name="mains")

    scenarios = build_k3_scenarios(
        mains, cutover_date="2014-04-15", coldstart_hours=20 * 24,
        monitoring_before_cutover_days=20, margin_after_days=10,
        step_injection_w=100.0, local_timezone="Europe/London",
    )
    control, step = scenarios["control"], scenarios["step"]
    cutover = pd.Timestamp("2014-04-15", tz="Europe/London").tz_convert("UTC")

    assert control.decision_times == step.decision_times
    assert step.target_series.loc[cutover] == 400.0
    assert step.target_series.loc[cutover - pd.Timedelta(hours=1)] == 300.0
    assert control.target_series.loc[cutover] == 300.0