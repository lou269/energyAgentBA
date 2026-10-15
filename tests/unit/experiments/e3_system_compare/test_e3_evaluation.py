# python -m pytest tests/unit/experiments/e3_system_compare -v

import pandas as pd

from experiments.e3_system_compare.e3_evaluation import RESULT_COLUMNS, summarize_e3
from src.common.timestamps import local_midnight_utc

TIMEZONE = "Europe/London"
CUTOVER = "2014-01-15"
SYSTEMS = ("SYS1", "SYS3")
LAST_DAY = 8
EVENT_SERIES = {"scaled": ((0, "scaled_strong"),), "ramp": ((0, "ramp_28"),)}


def _days(series: str) -> pd.DataFrame:
    # Tag -2 bis LAST_DAY je System, ohne Ereignis ist jeder Tag normal mit allen Skalen
    days = pd.DataFrame(
        [(config, day) for config in SYSTEMS for day in range(-2, LAST_DAY + 1)],
        columns=["config", "days_since_cutover"],
    )

    return days.assign(
        scenario=f"{series}_{CUTOVER}",
        series=series,
        cutover_date=CUTOVER,
        analyzed_day=[
            (pd.Timestamp(CUTOVER) + pd.Timedelta(days=day - 1)).strftime("%Y-%m-%d")
            for day in days["days_since_cutover"]
        ],
        decision_time=[
            local_midnight_utc(CUTOVER, TIMEZONE, days_offset=day).isoformat()
            for day in days["days_since_cutover"]
        ],
        classification="normal",
        classifier_called=False,
        adaption_action="none",
        day_error_w=100.0,
        mae_w=100.0,
        mape_pct=10.0,
        dominant_scale="daily",
        alarm=False,
        gate_open=False,
        sustained_drift=False,
        daily_score=0.0,
        weekday_score=0.0,
        weekly_score=0.0,
        long_term_deviation_pct=0.0,
        daily_sustained=False,
        weekday_sustained=False,
        weekly_sustained=False,
        long_term_sustained=False,
    ).reindex(columns=RESULT_COLUMNS)


def _set(
    results: pd.DataFrame,
    series: str,
    configs: tuple[str, ...],
    days: list[int],
    values: dict[str, str | float | bool],
) -> None:
    rows = (
        results["series"].eq(series)
        & results["config"].isin(configs)
        & results["days_since_cutover"].isin(days)
    )
    for column, value in values.items():
        results.loc[rows, column] = value


def _results() -> pd.DataFrame:
    return pd.concat(
        [_days(series) for series in ("control",) + tuple(EVENT_SERIES)],
        ignore_index=True,
    )


def _drift_with_reset(results: pd.DataFrame, series: str) -> None:
    # ab Tag 3 Drift aus weekly und long_term, SYS3 setzt zurück und prognostiziert danach besser
    _set(
        results,
        series,
        SYSTEMS,
        [3],
        {
            "gate_open": True,
            "sustained_drift": True,
            "weekly_sustained": True,
            "long_term_sustained": True,
            "classification": "new_pattern",
        },
    )
    _set(results, series, ("SYS3",), [3], {"adaption_action": "advance_history_start"})
    _set(results, series, ("SYS3",), [3, 4, 5, 6, 7, 8], {"day_error_w": 80.0})


OUTPUT_COLUMNS = [
    "scenario",
    "config",
    "decision_time",
    "analyzed_day",
    "classification",
    "explanation",
    "user_recommendation",
    "uncertainty",
    "evidence_paths",
]


def _summarize(results: pd.DataFrame):
    scenarios = [f"{series}_{CUTOVER}" for series in ("control",) + tuple(EVENT_SERIES)]
    runtimes = pd.DataFrame(
        {
            "scenario": scenarios * len(SYSTEMS),
            "config": [config for config in SYSTEMS for _ in scenarios],
            "runtime_seconds": 10.0,
            "interrupted": False,
        }
    )
    return summarize_e3(
        results,
        runtimes,
        pd.DataFrame(columns=OUTPUT_COLUMNS),
        event_series=EVENT_SERIES,
        reference_system="SYS1",
        llm_system="SYS3",
        week_days=7,
        smoothing_days=7,
        min_curve_cases=1,
    )


def test_only_cases_with_reset_count() -> None:
    results = _results()
    _drift_with_reset(results, "scaled")
    # vor dem Reset ist SYS3 an den Tagen 1 und 2 anders, das zählt nicht in den Vergleich
    _set(results, "scaled", ("SYS3",), [1, 2], {"day_error_w": 50.0})

    summary = _summarize(results)
    overall = summary.overall.set_index("config")
    cases = summary.cases.set_index("series")
    weeks = summary.forecast_weeks

    assert cases.loc["scaled", "triggered"]
    assert cases.loc["scaled", "reset_day"] == 3
    assert not cases.loc["ramp", "triggered"]
    assert overall.loc["SYS3", "triggered_cases"] == 1
    assert overall.loc["SYS1", "triggered_cases"] == 0
    assert overall.loc["SYS3", "cases"] == 2
    assert overall.loc["SYS3", "day_error_w"] == 80.0
    assert overall.loc["SYS1", "day_error_w"] == 100.0
    assert overall.loc["SYS3", "day_error_delta_w"] == -20.0
    assert overall.loc["SYS3", "paired_days"] == 6
    assert bool(overall.loc["SYS3", "day_error_reliable"])
    assert overall.loc["SYS3", "better_cases"] == 1
    assert list(weeks["week"]) == [1]
    assert list(weeks["cases"]) == [1]
    assert list(weeks["day_error_delta_w"]) == [-20.0]
    by_case = summary.forecast_weeks_by_case
    assert len(by_case) == 1
    assert by_case["series"].iloc[0] == "scaled"
    assert by_case["day_error_delta_w"].iloc[0] == -20.0


def test_no_reset_no_case() -> None:
    summary = _summarize(_results())
    overall = summary.overall.set_index("config")

    assert not summary.cases["triggered"].any()
    assert not summary.cases["better"].any()
    assert overall.loc["SYS3", "triggered_cases"] == 0
    assert summary.forecast.empty
    assert summary.forecast_weeks.empty


def test_better_through_fewer_notifications() -> None:
    results = _results()
    _drift_with_reset(results, "scaled")
    _set(results, "scaled", ("SYS3",), [3, 4, 5, 6, 7, 8], {"day_error_w": 100.0})
    # SYS1 meldet die Dauerlast an den Tagen danach weiter, mit Reset wird es ruhig
    _set(results, "scaled", ("SYS1",), [5, 6, 7], {"classification": "new_pattern"})
    # SYS3 ist nach dem Reset an zwei Tagen blind
    _set(results, "scaled", ("SYS3",), [4, 5], {"classification": "unknown"})

    summary = _summarize(results)
    case = summary.cases.set_index("series").to_dict("index")["scaled"]
    overall = summary.overall.set_index("config")

    assert not bool(case["day_error_reliable"])
    assert float(case["notification_delta"]) < 0
    assert bool(case["better"])
    assert list(overall["notification_window_days"]) == [5, 5]
    assert list(overall["notification_days"]) == [3, 0]
    assert list(overall["unknown_days"]) == [0, 2]
    weeks = summary.notifications_weeks.set_index("config")
    assert weeks.loc["SYS1", "week"] == 1
    assert weeks.loc["SYS1", "days"] == 5
    assert weeks.loc["SYS1", "new_pattern_days"] == 3
    assert weeks.loc["SYS1", "peak_days"] == 0
    assert weeks.loc["SYS3", "unknown_days"] == 2
    pooled = summary.notifications_weeks_pooled.set_index("config")
    assert pooled.loc["SYS1", "notification_share_pct"] == 60.0
    assert pooled.loc["SYS3", "unknown_share_pct"] == 40.0


def test_small_error_difference_is_not_better() -> None:
    results = _results()
    _drift_with_reset(results, "scaled")
    _set(results, "scaled", ("SYS3",), [3, 4, 5], {"day_error_w": 99.9})
    _set(results, "scaled", ("SYS3",), [6, 7, 8], {"day_error_w": 100.2})

    case = _summarize(results).cases.set_index("series").to_dict("index")["scaled"]

    assert not bool(case["day_error_reliable"])
    assert not bool(case["better"])
