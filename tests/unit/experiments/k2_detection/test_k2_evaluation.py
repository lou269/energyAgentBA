import pandas as pd

from experiments.k2_detection.k2_evaluation import (
    diagnosis_case,
    event_hits,
    events_in_range,
    find_real_events,
    summarize_grid,
    summarize_point,
)


def _chain(days: list[str], reset_days: list[str], alarm_days: list[str] | None = None):
    index = pd.to_datetime(days)
    return pd.DataFrame(
        {
            "analyzed_day": index,
            "reset": index.isin(pd.to_datetime(reset_days)),
            "alarm": index.isin(pd.to_datetime(alarm_days or [])),
            "daily_sustained": False,
            "weekday_sustained": True,
            "weekly_sustained": True,
            "long_term_sustained": False,
        }
    )


def _events(starts: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "start": pd.to_datetime(starts),
            "direction": 1,
            "change_pct": 30.0,
        }
    )


def _step_series() -> pd.Series:
    # Niveau 200 W, ab Tag 100 280 W, dazu ein Einbruch von 5 Tagen bei Tag 40
    index = pd.date_range("2020-01-01", periods=24 * 200, freq="1h", tz="UTC")
    series = pd.Series(200.0, index=index)
    series.iloc[24 * 100 :] = 280.0
    series.iloc[24 * 40 : 24 * 45] = 100.0
    return series


def test_find_real_events() -> None:
    events = find_real_events(
        _step_series(),
        local_timezone="UTC",
        reference_days=28,
        transition_days=28,
        min_change_pct=20.0,
        min_duration_days=10,
        smoothing_days=7,
        share=0.75,
        merge_days=28,
    )

    assert len(events) == 1
    assert events.loc[0, "direction"] == 1
    # Beginn liegt am Tag der Stufe, nicht Wochen davor
    assert abs((events["start"].iloc[0] - pd.Timestamp("2020-04-10")).days) <= 3


def test_events_in_range() -> None:
    events = _events(["2020-01-05", "2020-03-01", "2020-05-20"])

    inside = events_in_range(
        events,
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-06-01"),
        hit_days_before=10,
        hit_days_after=28,
    )

    # der erste beginnt zu früh (Fenster vor dem ersten Tag), der letzte endet nach dem letzten Tag
    assert inside["start"].tolist() == [pd.Timestamp("2020-03-01")]


def test_summarize_point() -> None:
    days = [str(day.date()) for day in pd.date_range("2020-01-01", periods=365)]
    events = _events(["2020-03-01", "2020-08-01"])
    chain = _chain(days, ["2020-03-10", "2020-03-12", "2020-05-15", "2020-12-01"])

    point = summarize_point(chain, events, hit_days_before=10, hit_days_after=28)
    hits = event_hits(chain, events, hit_days_before=10, hit_days_after=28)

    # erster Reset im Fenster ist der Treffer, der zweite im selben Fenster ist nicht falsch
    assert hits["delay"].iloc[0] == 9
    assert pd.isna(hits["reset_day"].iloc[1])
    assert point["hits"] == 1
    assert point["events"] == 2
    assert point["false_resets"] == 2
    assert point["false_per_year"] == 2 * 365.25 / 365


def test_summarize_grid() -> None:
    points = pd.DataFrame(
        {
            "weekday_streak_threshold": [1.25, 2.5],
            "weekly_streak_threshold": [1.0, 0.75],
            "long_term_streak_threshold_pct": [25.0, 20.0],
            "hits": [2, 4],
            "events": [6, 6],
            "mean_delay": [10.0, 15.0],
            "resets": [3, 8],
            "false_resets": [1, 6],
            "false_per_year": [0.5, 3.1],
        }
    )

    summary = summarize_grid(
        points, 1.5, {"weekday": 2.5, "weekly": 0.75, "long_term": 20.0}
    )

    # der Punkt über der Grenze steht hinten, auch wenn er mehr trifft
    assert summary.selected == {"weekday": 1.25, "weekly": 1.0, "long_term": 25.0}
    assert summary.ranked["selected"].tolist() == [True, False]
    assert summary.ranked["current"].tolist() == [False, True]


def _case(chain: pd.DataFrame, kind: str) -> dict:
    # Cutover 2020-02-01, ein echter Trend am 2020-03-01
    return diagnosis_case(
        chain,
        "2020-02-01",
        kind,
        events=_events(["2020-03-01"]),
        positive_kinds=("scaled",),
        negative_kinds=("ramp_56",),
        hit_days_before=10,
        hit_days_after=28,
    )


def test_diagnosis_case() -> None:
    days = [str(day.date()) for day in pd.date_range("2020-01-01", periods=90)]

    # Entscheidungstag = analysierter Tag + 1: der Reset am 5.2. ist Tag 5, die Spitze vom 1.2. Tag 1
    positive = _case(_chain(days, ["2020-02-05"]), "scaled")
    too_late = _case(_chain(days, ["2020-03-20"]), "scaled")
    slow_fired = _case(_chain(days, ["2020-02-15"]), "ramp_56")
    # liegt im Trefferfenster eines echten Trends
    slow_in_event = _case(_chain(days, ["2020-03-05"]), "ramp_56")
    peak = _case(_chain(days, [], alarm_days=["2020-02-01"]), "peak")

    assert positive["hit_day"] == 5
    assert positive["scales"] == "weekday+weekly"
    assert pd.isna(too_late["hit_day"])
    assert slow_fired["hit_day"] == 15
    assert pd.isna(slow_in_event["hit_day"])
    assert peak["hit_day"] == 1
