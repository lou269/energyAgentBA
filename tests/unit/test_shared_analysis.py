# python -m pytest tests/unit/test_shared_analysis.py -v

import pandas as pd
import pytest

from experiments.shared_analysis import (
    analyzed_days_since_event,
    compare_mae_to_reference,
    compare_mae_to_reference_after_adaption,
    count_days_by_period,
    count_notifications,
    forecast_days_since_event,
    spread_over_repeats,
)
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"
# Zeitumstellung am 30.03.2014, der Tag hat nur 23 Stunden
EVENT_TIME = local_midnight_utc("2014-03-31", TIMEZONE)


def _comparison(
    config: str,
    mae: list[float],
    classifications: list[str | None],
    adaptions: list[str],
) -> pd.DataFrame:
    decision_times = local_calendar_range(
        local_midnight_utc("2014-03-29", TIMEZONE),
        1,
        local_midnight_utc("2014-04-02", TIMEZONE),
        TIMEZONE,
    )
    return pd.DataFrame(
        {
            "decision_time": decision_times,
            "config": config,
            "classification": classifications,
            "adaption_action": adaptions,
            "error": None,
            "mae_w": mae,
        }
    )


def test_days_since_event_count_calendar_days_across_dst() -> None:
    comparison = _comparison("SYS2", [100.0] * 5, [None] * 5, ["none"] * 5)

    # decision_time 31.03. 00:00 bewertet den 30.03., prognostiziert aber schon den 31.03.
    assert list(analyzed_days_since_event(comparison, EVENT_TIME, TIMEZONE)) == [
        -3,
        -2,
        -1,
        0,
        1,
    ]
    assert list(forecast_days_since_event(comparison, EVENT_TIME, TIMEZONE)) == [
        -2,
        -1,
        0,
        1,
        2,
    ]


def test_count_days_by_period_splits_on_analyzed_day() -> None:
    comparison = _comparison(
        "SYS2",
        [100.0] * 5,
        ["normal", "new_pattern", "normal", "new_pattern", "new_pattern"],
        ["none", "reset", "none", "none", "reset"],
    )

    counts = count_days_by_period(comparison, EVENT_TIME, TIMEZONE).set_index("period")
    counts = counts[["days", "new_pattern", "normal", "adaption_days"]].to_dict("index")

    assert counts["before_event"] == {
        "days": 3,
        "new_pattern": 1,
        "normal": 2,
        "adaption_days": 1,
    }
    assert counts["after_event"] == {
        "days": 2,
        "new_pattern": 2,
        "normal": 0,
        "adaption_days": 1,
    }


def test_compare_mae_to_reference_pairs_days_from_event_on() -> None:
    no_adaption = ["none"] * 5
    comparison = pd.concat(
        [
            _comparison(
                "SYS1", [50.0, 50.0, 100.0, 100.0, 100.0], [None] * 5, no_adaption
            ),
            _comparison(
                "SYS3", [10.0, 10.0, 90.0, 110.0, 70.0], ["normal"] * 5, no_adaption
            ),
        ]
    )

    result = (
        compare_mae_to_reference(comparison, EVENT_TIME, "SYS1")
        .set_index("config")
        .to_dict("index")["SYS3"]
    )

    assert result["paired_count"] == 3
    assert result["mean_delta"] == -10.0
    assert result["better_share"] == 2 / 3
    assert not result["exceeds_noise"]


def test_after_adaption_starts_with_the_first_adaption_from_the_event_on() -> None:
    comparison = pd.concat(
        [
            _comparison(
                "SYS1", [50.0, 50.0, 100.0, 100.0, 100.0], [None] * 5, ["none"] * 5
            ),
            # die Adaption vor dem Event zählt nicht, die erste danach bewertet den 31.03. und prognostiziert den 01.04.
            _comparison(
                "SYS2",
                [50.0, 40.0, 90.0, 80.0, 110.0],
                ["normal"] * 5,
                ["none", "reset", "none", "reset", "reset"],
            ),
        ]
    )

    result = (
        compare_mae_to_reference_after_adaption(
            comparison, EVENT_TIME, "SYS1", TIMEZONE
        )
        .set_index("config")
        .to_dict("index")["SYS2"]
    )

    assert result["adaption_forecast_day"] == 1
    assert result["paired_count"] == 2
    assert result["mean_delta"] == -5.0
    assert result["better_share"] == 0.5
    assert result["reference_mean_mae_w"] == 100.0


def test_notifications_count_unknown_separately_and_scale_to_the_period() -> None:
    results = pd.DataFrame(
        {
            "mode": "adaption",
            "classification": [
                "normal",
                "peak",
                "new_pattern",
                "unknown",
                "normal",
                "low",
            ],
        }
    )

    counts = count_notifications(
        results,
        ["mode"],
        notification_classes=("peak", "low", "new_pattern"),
        period_days=30,
    ).to_dict("records")[0]

    assert counts["notification_days"] == 3
    assert counts["unknown_days"] == 1
    assert counts["notifications_per_period"] == 15.0


def test_spread_over_repeats_counts_repeats_in_direction_of_the_mean() -> None:
    summary = pd.DataFrame(
        {
            "strategy": "cut",
            "cutover_date": ["2013-10-15", "2014-01-15", "2014-04-15", "2014-07-15"],
            "delta": [-3.0, -2.0, 1.0, float("nan")],
        }
    )

    row = spread_over_repeats(
        summary, ["strategy"], "delta", count_same_direction=True
    ).to_dict("records")[0]

    assert row["mean"] == pytest.approx(-4 / 3)
    # der fehlende Cutover zählt weder mit noch als Gegenrichtung
    assert row["same_direction"] == "2/3"
