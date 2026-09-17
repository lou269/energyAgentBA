# python -m pytest tests/unit/common/test_timestamps.py -v

from __future__ import annotations

import pandas as pd

from src.common.timestamps import local_calendar_range, snap_to_local_midnight_range


def test_snap_to_local_midnight_range_leaves_exact_midnight_untouched() -> None:
    start = pd.Timestamp("2020-01-01T00:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-01-10T00:00:00", tz="Europe/London").tz_convert("UTC")

    snapped_start, snapped_end = snap_to_local_midnight_range(start, end, "Europe/London")

    assert snapped_start == start
    assert snapped_end == end


def test_snap_to_local_midnight_range_rounds_a_partial_day_in() -> None:
    start = pd.Timestamp("2020-01-01T13:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-01-10T05:00:00", tz="Europe/London").tz_convert("UTC")

    snapped_start, snapped_end = snap_to_local_midnight_range(start, end, "Europe/London")

    assert snapped_start.tz_convert("Europe/London") == pd.Timestamp("2020-01-02T00:00:00", tz="Europe/London")
    assert snapped_end.tz_convert("Europe/London") == pd.Timestamp("2020-01-10T00:00:00", tz="Europe/London")


def test_snap_to_local_midnight_range_across_dst_spring_forward() -> None:
    # 2020-03-29: Europe/London stellt die Uhr um 01:00 auf 02:00 vor, der Tag hat nur 23 Stunden
    start = pd.Timestamp("2020-03-28T22:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-04-01T00:00:00", tz="Europe/London").tz_convert("UTC")

    snapped_start, snapped_end = snap_to_local_midnight_range(start, end, "Europe/London")

    assert snapped_start.tz_convert("Europe/London") == pd.Timestamp("2020-03-29T00:00:00", tz="Europe/London")
    assert snapped_end.tz_convert("Europe/London") == pd.Timestamp("2020-04-01T00:00:00", tz="Europe/London")


def test_local_calendar_range_spans_dst_spring_forward_as_24_local_days() -> None:
    start = pd.Timestamp("2020-03-27T00:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-03-31T00:00:00", tz="Europe/London").tz_convert("UTC")

    result = local_calendar_range(start, 24, end, "Europe/London")

    local_times = result.tz_convert("Europe/London")
    assert list(local_times.hour) == [0, 0, 0, 0, 0]
    # der DST-Tag selbst hat real nur 23 Stunden
    assert (result[3] - result[2]) == pd.Timedelta(hours=23)


def test_local_calendar_range_spans_dst_fall_back_as_24_local_days() -> None:
    # 2020-10-25: Europe/London stellt die Uhr um 02:00 auf 01:00 zurück, der Tag hat 25 Stunden
    start = pd.Timestamp("2020-10-23T00:00:00", tz="Europe/London").tz_convert("UTC")
    end = pd.Timestamp("2020-10-27T00:00:00", tz="Europe/London").tz_convert("UTC")

    result = local_calendar_range(start, 24, end, "Europe/London")

    local_times = result.tz_convert("Europe/London")
    assert list(local_times.hour) == [0, 0, 0, 0, 0]
    assert (result[3] - result[2]) == pd.Timedelta(hours=25)


def test_local_calendar_range_leaves_non_24_multiples_identical_to_a_plain_date_range() -> None:
    start = pd.Timestamp("2020-03-28T00:00:00", tz="UTC")
    end = pd.Timestamp("2020-03-31T00:00:00", tz="UTC")

    result = local_calendar_range(start, 3, end, "Europe/London")
    expected = pd.date_range(start=start, end=end, freq="3h")

    assert result.equals(expected)
