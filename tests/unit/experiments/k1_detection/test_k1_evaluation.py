import numpy as np
import pandas as pd

from experiments.k1_detection.k1_evaluation import (
    diagnosis_case,
    summarize_diagnosis,
    summarize_grid,
    sustained_values,
    thresholds_for_share,
)


def test_sustained_values() -> None:
    index = pd.date_range("2020-01-01", periods=7)
    values = pd.DataFrame(
        {"weekly": [1.0, -2.0, 3.0, 4.0, 5.0, 6.0, np.nan]}, index=index
    )

    sustained = sustained_values(values, window_days=7, min_days=6)

    # 6 gültige Tage, der kleinste Betrag reicht für 6 von 7
    assert sustained["weekly"].iloc[-1] == 1.0
    assert sustained["weekly"].iloc[:5].isna().all()


def test_thresholds_for_share() -> None:
    sustained = pd.DataFrame({"weekly": [np.nan] + list(np.arange(1.0, 100.0))})

    threshold = thresholds_for_share(sustained, 0.1)["weekly"]

    assert sustained["weekly"].ge(threshold).mean() == 0.1


def test_summarize_grid() -> None:
    grid = pd.DataFrame(
        {
            "share": [0.05, 0.10, 0.15],
            "weekly_streak_threshold": [2.0, 1.5, 1.0],
            "long_term_streak_threshold_pct": [20.0, 17.0, 14.0],
        }
    )
    resets = pd.DataFrame(
        {"share": [0.10, 0.15, 0.15, 0.15], "analyzed_day": pd.Timestamp("2020-01-01")}
    )

    summary = summarize_grid(grid, resets, days=730, max_resets=2)

    assert summary["resets"].tolist() == [0, 1, 3]
    assert summary.loc[summary["selected"], "share"].tolist() == [0.10]


def _chain(reset_days: list[str], alarm_days: list[str]) -> pd.DataFrame:
    days = pd.date_range("2020-01-01", periods=60)
    return pd.DataFrame(
        {
            "analyzed_day": days,
            "reset": days.isin(pd.to_datetime(reset_days)),
            "alarm": days.isin(pd.to_datetime(alarm_days)),
        }
    )


def test_diagnosis_counts_only_resets_before_the_control() -> None:
    cutover = "2020-01-20"
    cases = pd.DataFrame(
        [
            diagnosis_case(_chain(["2020-02-10"], []), cutover, "control"),
            diagnosis_case(_chain(["2020-02-01"], []), cutover, "scaled"),
            diagnosis_case(_chain(["2020-02-15"], []), cutover, "ramp_56"),
            diagnosis_case(_chain([], ["2020-01-20"]), cutover, "peak"),
        ]
    ).assign(config="chosen")

    diagnosis = summarize_diagnosis(cases).set_index("kind")

    # Ereignistag (Cutover) ist Tag 1
    assert diagnosis.loc["scaled", "own_resets"] == 1
    assert diagnosis.loc["scaled", "median_reset_day"] == 13
    assert diagnosis.loc["ramp_56", "own_resets"] == 0
    assert diagnosis.loc["ramp_56", "expected"] == "silent"
    assert diagnosis.loc["peak", "event_alarms"] == 1
    assert diagnosis.loc["control", "own_resets"] == 0
