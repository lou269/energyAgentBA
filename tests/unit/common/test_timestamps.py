# python -m pytest tests/unit/common/test_timestamps.py -v

from __future__ import annotations

import pandas as pd
import pytest

from src.common.timestamps import (
    analyzed_day,
    analyzed_day_text,
    local_calendar_range,
    local_date_text,
    local_day_hours,
    local_days_between,
    local_isoformat,
    local_midnight_utc,
    parse_utc_timestamp_field,
    reindex_at_local_lag,
    shift_local_days,
    snap_to_local_midnight_range,
)


def test_snap_to_local_midnight_range_leaves_exact_midnight_untouched() -> None:
    start = pd.Timestamp("2020-01-01T00:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-01-10T00:00:00", tz="Europe/London").tz_convert("UTC")

    snapped_start, snapped_end = snap_to_local_midnight_range(
        start, end, "Europe/London"
    )

    assert snapped_start == start
    assert snapped_end == end


def test_snap_to_local_midnight_range_rounds_a_partial_day_in() -> None:
    start = pd.Timestamp("2020-01-01T13:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-01-10T05:00:00", tz="Europe/London").tz_convert("UTC")

    snapped_start, snapped_end = snap_to_local_midnight_range(
        start, end, "Europe/London"
    )

    assert snapped_start.tz_convert("Europe/London") == pd.Timestamp(
        "2020-01-02T00:00:00", tz="Europe/London"
    )
    assert snapped_end.tz_convert("Europe/London") == pd.Timestamp(
        "2020-01-10T00:00:00", tz="Europe/London"
    )


def test_snap_to_local_midnight_range_across_dst_spring_forward() -> None:
    # 2020-03-29: Europe/London stellt die Uhr um 01:00 auf 02:00 vor, der Tag hat nur 23 Stunden
    start = pd.Timestamp("2020-03-28T22:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-04-01T00:00:00", tz="Europe/London").tz_convert("UTC")

    snapped_start, snapped_end = snap_to_local_midnight_range(
        start, end, "Europe/London"
    )

    assert snapped_start.tz_convert("Europe/London") == pd.Timestamp(
        "2020-03-29T00:00:00", tz="Europe/London"
    )
    assert snapped_end.tz_convert("Europe/London") == pd.Timestamp(
        "2020-04-01T00:00:00", tz="Europe/London"
    )


def test_local_calendar_range_spans_dst_spring_forward_as_local_days() -> None:
    start = pd.Timestamp("2020-03-27T00:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-03-31T00:00:00", tz="Europe/London").tz_convert("UTC")

    result = local_calendar_range(start, 1, end, "Europe/London")

    local_times = result.tz_convert("Europe/London")
    assert list(local_times.hour) == [0, 0, 0, 0, 0]
    # der DST-Tag selbst hat real nur 23 Stunden
    assert (result[3] - result[2]) == pd.Timedelta(hours=23)


def test_local_calendar_range_spans_dst_fall_back_as_local_days() -> None:
    # 2020-10-25: Europe/London stellt die Uhr um 02:00 auf 01:00 zurück, der Tag hat 25 Stunden
    start = pd.Timestamp("2020-10-23T00:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-10-27T00:00:00", tz="Europe/London").tz_convert("UTC")

    result = local_calendar_range(start, 1, end, "Europe/London")

    local_times = result.tz_convert("Europe/London")
    assert list(local_times.hour) == [0, 0, 0, 0, 0]
    assert (result[3] - result[2]) == pd.Timedelta(hours=25)


def test_local_calendar_range_rejects_utc_midnight_in_summer() -> None:
    # 00:00 UTC ist im Sommer 01:00 Ortszeit, jeder Tag der Reihe wäre um eine Stunde versetzt
    start = pd.Timestamp("2014-04-15T00:00:00", tz="UTC")

    with pytest.raises(ValueError, match="local midnight"):
        local_calendar_range(start, 1, start + pd.Timedelta(days=5), "Europe/London")


@pytest.mark.parametrize(
    ("date", "expected_hours"),
    [("2020-03-29", 23), ("2020-06-01", 24), ("2020-10-25", 25)],
)
def test_local_day_hours_cover_exactly_one_local_day(
    date: str, expected_hours: int
) -> None:
    day_start = local_midnight_utc(date, "Europe/London")

    hours = local_day_hours(day_start, 1, "1h", "Europe/London")

    assert len(hours) == expected_hours
    assert hours[-1] + pd.Timedelta(hours=1) == shift_local_days(
        day_start, 1, "Europe/London"
    )


def test_shift_local_days_keeps_local_midnight_across_dst() -> None:
    decision_time = local_midnight_utc("2020-04-02", "Europe/London")

    shifted = shift_local_days(decision_time, -7, "Europe/London")

    assert shifted.tz_convert("Europe/London") == pd.Timestamp(
        "2020-03-26T00:00:00", tz="Europe/London"
    )
    assert decision_time - shifted == pd.Timedelta(hours=7 * 24 - 1)


def test_analyzed_day_is_the_local_day_before_decision_time() -> None:
    decision_time = local_midnight_utc("2020-06-15", "Europe/London")

    assert decision_time.hour == 23
    assert (
        analyzed_day(decision_time, "Europe/London").date()
        == pd.Timestamp("2020-06-14").date()
    )


def test_local_timestamp_field_round_trips_to_utc() -> None:
    timestamp = local_midnight_utc("2020-06-15", "Europe/London")
    value = local_isoformat(timestamp, "Europe/London")

    assert value == "2020-06-15T00:00:00+01:00"
    assert parse_utc_timestamp_field(value, "field") == timestamp


@pytest.mark.parametrize(
    ("target_local", "expected_local"),
    [
        ("2020-03-30T08:00", "2020-03-29T08:00"),
        # 01:00 gab es am 29.03. nicht, genommen wird die Stunde davor
        ("2020-03-30T01:00", "2020-03-29T00:00"),
        # am 25.10. gibt es 01:00 zweimal, genommen wird die erste (noch Sommerzeit)
        ("2020-10-26T01:00", "2020-10-25T01:00"),
    ],
)
def test_reindex_at_local_lag_keeps_the_local_time_across_dst(
    target_local: str, expected_local: str
) -> None:
    index = pd.date_range(
        local_midnight_utc("2020-03-28", "Europe/London"),
        local_midnight_utc("2020-10-27", "Europe/London"),
        freq="1h",
        inclusive="left",
    )
    series = pd.Series(range(len(index)), index=index, dtype="float64")
    target_index = pd.DatetimeIndex(
        [pd.Timestamp(target_local).tz_localize("Europe/London")]
    ).tz_convert("UTC")

    result = reindex_at_local_lag(series, target_index, 1, "Europe/London")

    assert (
        result.iloc[0]
        == series.loc[
            pd.Timestamp(expected_local).tz_localize("Europe/London", ambiguous=True)
        ]
    )


def test_days_between_across_dst() -> None:
    # der 30.03.2014 hat nur 23 Stunden, gezählt werden trotzdem Kalendertage
    earlier = local_midnight_utc("2014-03-29", "Europe/London")
    later = local_midnight_utc("2014-03-31", "Europe/London")

    assert local_days_between(later, earlier, "Europe/London") == 2


def test_date_texts_are_local() -> None:
    # lokale Mitternacht im Sommer ist 23:00 UTC am Vortag
    midnight = local_midnight_utc("2014-04-15", "Europe/London")

    assert local_date_text(midnight, "Europe/London") == "2014-04-15"
    assert analyzed_day_text(midnight, "Europe/London") == "2014-04-14"
