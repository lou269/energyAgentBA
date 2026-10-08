# python -m pytest tests/unit/experiments/e3_system_compare -v

import pandas as pd

from experiments.e3_system_compare.e3_evaluation import RESULT_COLUMNS, summarize_e3
from src.common.timestamps import local_midnight_utc

TIMEZONE = "Europe/London"
CUTOVER = "2014-01-15"
SYSTEMS = ("SYS1", "SYS2", "SYS3")
LAST_DAY = 8


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
    configs: tuple[str, ...],
    days: list[int],
    values: dict[str, str | float | bool],
) -> None:
    rows = (
        results["series"].eq("events")
        & results["config"].isin(configs)
        & results["days_since_cutover"].isin(days)
    )
    for column, value in values.items():
        results.loc[rows, column] = value


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


def _summarize(
    results: pd.DataFrame,
    events: tuple[tuple[int, str], ...],
    llm_outputs: pd.DataFrame | None = None,
):
    runtimes = pd.DataFrame(
        {
            "scenario": [f"{series}_{CUTOVER}" for series in ("control", "events")] * 3,
            "config": [config for config in SYSTEMS for _ in range(2)],
            "runtime_seconds": 10.0,
            "interrupted": False,
        }
    )
    return summarize_e3(
        results,
        runtimes,
        pd.DataFrame(columns=OUTPUT_COLUMNS) if llm_outputs is None else llm_outputs,
        events=events,
        reference_system="SYS1",
        rule_system="SYS2",
        llm_system="SYS3",
        single_day_scales=["daily", "weekday"],
    )


def _results() -> pd.DataFrame:
    return pd.concat([_days("control"), _days("events")], ignore_index=True)


def test_durable_judged_at_drift() -> None:
    results = _results()
    # Tag 1 nur ein Alarm, die Regel sagt peak, ab Tag 3 Drift aus weekly und long_term
    _set(
        results,
        SYSTEMS,
        [1],
        {"alarm": True, "gate_open": True, "classification": "peak"},
    )
    _set(
        results,
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
    _set(results, ("SYS2",), [3], {"adaption_action": "advance_history_start"})
    # das LLM hält die Drift für eine Spitze und setzt nicht zurück
    _set(results, ("SYS3",), [3], {"classification": "peak"})

    events = _summarize(results, ((0, "scaled_strong"),)).events.set_index("config")

    assert events.loc["SYS2", "judged_day"] == 3
    assert events.loc["SYS2", "trigger_scale"] == "weekly+long_term"
    assert bool(events.loc["SYS2", "correct"])
    assert events.loc["SYS2", "lead_notification_days"] == 1
    assert events.loc["SYS2", "correct_action"]
    assert not bool(events.loc["SYS3", "correct"])
    assert not events.loc["SYS1", "correct_action"]


def test_false_reset_separation() -> None:
    results = _results()
    _set(
        results,
        SYSTEMS,
        [1, 5],
        {"alarm": True, "gate_open": True, "classification": "peak"},
    )
    _set(results, SYSTEMS, [2], {"gate_open": True, "sustained_drift": True})
    _set(results, ("SYS1", "SYS2"), [2], {"classification": "new_pattern"})
    _set(results, ("SYS2",), [2], {"adaption_action": "advance_history_start"})
    _set(results, ("SYS3",), [2], {"classification": "peak"})
    _set(results, ("SYS2",), [2, 3, 4, 5], {"day_error_w": 80.0, "mae_w": 80.0})

    summary = _summarize(
        results, ((0, "peak_strong"), (4, "peak_strong"), (7, "scaled_strong"))
    )
    events = summary.events.set_index(["event", "config"])
    separations = summary.separations.set_index("series")
    decision = summary.decisions.iloc[0]

    assert not events.loc[(1, "SYS2"), "correct_action"]
    assert events.loc[(1, "SYS3"), "correct_action"]
    assert not events.loc[(1, "SYS2"), "after_separation"]
    assert events.loc[(2, "SYS3"), "after_separation"]
    assert separations.loc["events", "separation_day"] == 2
    assert separations.loc["events", "forecast_identical_before"]
    assert pd.isna(separations.loc["control", "separation_day"])
    assert not decision["rule_better"]
    assert decision["rule_single_day_resets"] == 1
    assert decision["llm_single_day_resets"] == 0
    assert not decision["llm_better"]


def test_stuck_only_in_tf3() -> None:
    results = _results()
    # Festhänger an Tag 3, eingeordnet an Tag 4, das Flag öffnet das Gate bei allen
    _set(
        results,
        SYSTEMS,
        [4],
        {"gate_open": True, "classification": "measurement_error"},
    )
    _set(
        results,
        ("SYS3",),
        [4],
        {"classification": "new_pattern", "adaption_action": "advance_history_start"},
    )

    summary = _summarize(results, ((3, "stuck"), (6, "scaled_strong")))
    events = summary.events.loc[summary.events["event"].eq(1)].set_index("config")
    criteria = summary.criteria.set_index(["config", "expected"])

    assert events.loc["SYS2", "judged_day"] == 4
    assert bool(events.loc["SYS2", "correct"])
    assert events.loc["SYS2", "correct_action"]
    assert not bool(events.loc["SYS3", "correct"])
    assert not events.loc["SYS3", "correct_action"]
    # die Dauerlast bleibt unentdeckt, der Festhänger zählt nicht in TF2
    assert criteria.loc[("SYS2", "all"), "prefilter_events"] == 1
    assert criteria.loc[("SYS2", "all"), "prefilter_detected"] == 0
    assert criteria.loc[("SYS2", "all"), "detected"] == 1
    assert criteria.loc[("SYS2", "all"), "correct"] == 1
    assert summary.decisions.iloc[0]["rule_single_day_resets"] == 0


def test_llm_answers() -> None:
    results = _results()
    _set(results, ("SYS2",), [4], {"classification": "peak"})
    _set(
        results,
        ("SYS3",),
        [4],
        {"classification": "new_pattern", "adaption_action": "advance_history_start"},
    )
    outputs = pd.DataFrame(
        [
            {
                "scenario": f"events_{CUTOVER}",
                "config": "SYS3",
                "decision_time": "2014-01-19T00:00:00+00:00",
                "analyzed_day": "2014-01-18",
                "classification": "new_pattern",
                "explanation": "Text",
                "user_recommendation": "Rat",
                "uncertainty": "Unsicher",
                "evidence_paths": "anomaly.level",
            }
        ]
    )

    answers = _summarize(
        results, ((3, "peak_strong"), (6, "scaled_strong")), outputs
    ).answers

    assert len(answers) == 1
    answer = answers.iloc[0]
    assert answer["event"] == 1
    assert answer["days_since_cutover"] == 4
    assert answer["rule_classification"] == "peak"
    assert answer["adaption_action"] == "advance_history_start"
