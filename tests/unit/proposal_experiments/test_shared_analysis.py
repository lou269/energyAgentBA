# python -m pytest tests/unit/proposal_experiments/test_shared_analysis.py -v

import pandas as pd

from experiments.proposal_experiments.shared_analysis import (
    analyzed_days_since_event,
    compare_mae_to_reference,
    count_days_by_period,
    forecast_days_since_event,
)
from src.common.timestamps import local_calendar_range, local_midnight_utc

TIMEZONE = "Europe/London"
# Zeitumstellung am 30.03.2014, der Tag hat nur 23 Stunden
EVENT_TIME = local_midnight_utc("2014-03-31", TIMEZONE)


def _comparison(config: str, mae: list[float], classifications: list[str | None], adaptions: list[str]) -> pd.DataFrame:
    decision_times = local_calendar_range(local_midnight_utc("2014-03-29", TIMEZONE), 1, local_midnight_utc("2014-04-02", TIMEZONE), TIMEZONE)
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
    assert list(analyzed_days_since_event(comparison, EVENT_TIME, TIMEZONE)) == [-3, -2, -1, 0, 1]
    assert list(forecast_days_since_event(comparison, EVENT_TIME, TIMEZONE)) == [-2, -1, 0, 1, 2]


def test_count_days_by_period_splits_on_analyzed_day() -> None:
    comparison = _comparison(
        "SYS2", [100.0] * 5,
        ["normal", "new_pattern", "normal", "new_pattern", "new_pattern"],
        ["none", "reset", "none", "none", "reset"],
    )

    counts = count_days_by_period(comparison, EVENT_TIME, TIMEZONE).set_index("period")

    assert counts.loc["before_event", ["days", "new_pattern", "normal", "adaption_days"]].tolist() == [3, 1, 2, 1]
    assert counts.loc["after_event", ["days", "new_pattern", "normal", "adaption_days"]].tolist() == [2, 2, 0, 1]


def test_compare_mae_to_reference_pairs_days_from_event_on() -> None:
    no_adaption = ["none"] * 5
    comparison = pd.concat(
        [
            _comparison("SYS1", [50.0, 50.0, 100.0, 100.0, 100.0], [None] * 5, no_adaption),
            _comparison("SYS3", [10.0, 10.0, 90.0, 110.0, 70.0], ["normal"] * 5, no_adaption),
        ]
    )

    result = compare_mae_to_reference(comparison, EVENT_TIME, "SYS1").set_index("config").loc["SYS3"]

    assert result["paired_count"] == 3
    assert result["mean_delta"] == -10.0
    assert result["better_share"] == 2 / 3
    assert not result["exceeds_noise"]
