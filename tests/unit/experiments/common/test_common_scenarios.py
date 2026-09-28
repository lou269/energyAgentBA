# python -m pytest tests/unit/experiments/common/test_common_scenarios.py -v

import pandas as pd

from experiments.common.scenarios import (
    build_decision_times,
    crop_history_for_coldstart,
    slice_history_window,
    subtract_channels_in_window,
)


def test_build_decision_times_applies_margins_on_both_sides() -> None:
    # Winter, Ortszeit London = UTC
    window_start = pd.Timestamp("2020-01-06T00:00:00+00:00")
    window_end = pd.Timestamp("2020-01-13T00:00:00+00:00")

    decision_times = build_decision_times(
        window_start, window_end, margin_before_days=7, margin_after_days=4
    )

    assert decision_times[0] == window_start - pd.Timedelta(days=7)
    assert decision_times[-1] == window_end + pd.Timedelta(days=4)
    assert all(
        second - first == pd.Timedelta(hours=24)
        for first, second in zip(decision_times, decision_times[1:])
    )


def test_build_decision_times_stay_on_local_midnight_across_dst() -> None:
    # Mitternacht BST, 60 Tage davor ist noch GMT
    cutover = pd.Timestamp("2014-04-15", tz="Europe/London").tz_convert("UTC")

    decision_times = build_decision_times(
        cutover, cutover, margin_before_days=60, margin_after_days=0
    )

    assert {time.tz_convert("Europe/London").hour for time in decision_times} == {0}
    assert cutover in decision_times


def _mains(hours: int, value: float = 300.0) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    return pd.Series(value, index=index, name="mains")


def test_subtract_channels_in_window_only_affects_the_window() -> None:
    mains = _mains(48)
    appliance = pd.DataFrame({"H1_M5": 50.0}, index=mains.index)
    window_start, window_end = mains.index[10], mains.index[20]

    adjusted = subtract_channels_in_window(
        mains, appliance, ["H1_M5"], window_start=window_start, window_end=window_end
    )

    assert (
        adjusted.loc[window_start : window_end - pd.Timedelta(hours=1)] == 250.0
    ).all()
    assert (adjusted.loc[:window_start].iloc[:-1] == 300.0).all()
    assert (adjusted.loc[window_end:] == 300.0).all()


def test_subtract_channels_in_window_clips_at_zero() -> None:
    mains = _mains(24, value=30.0)
    appliance = pd.DataFrame({"H1_M5": 50.0}, index=mains.index)
    window_start, window_end = mains.index[0], mains.index[-1]

    adjusted = subtract_channels_in_window(
        mains, appliance, ["H1_M5"], window_start=window_start, window_end=window_end
    )

    assert (
        adjusted.loc[window_start : window_end - pd.Timedelta(hours=1)] == 0.0
    ).all()


def test_slice_history_window_takes_history_days_before_start_and_end_inclusive() -> (
    None
):
    series = _mains(24 * 10)
    imputed = pd.Series(False, index=series.index)
    start, end = series.index[24 * 5], series.index[24 * 7 - 1]

    history, targets, targets_imputed = slice_history_window(
        series, imputed, start=start, end=end, history_days=2
    )

    assert history.index[0] == start - pd.Timedelta(days=2)
    assert history.index[-1] == start - pd.Timedelta(hours=1)
    assert len(targets) == len(targets_imputed) == 48


def test_slice_history_window_without_history_days_keeps_everything_before_start() -> (
    None
):
    series = _mains(24 * 10)
    imputed = pd.Series(False, index=series.index)
    start = series.index[24 * 5]

    history, _targets, _imputed = slice_history_window(
        series, imputed, start=start, end=series.index[-1], history_days=None
    )

    assert history.index[0] == series.index[0]
    assert len(history) == 24 * 5


def test_coldstart_history_counts_local_days_across_the_clock_change() -> None:
    index = pd.date_range("2014-03-01", "2014-04-30", freq="1h", tz="UTC")
    series = pd.Series(300.0, index=index)
    # Mitternacht Ortszeit am 03.04., Sommerzeit
    first_decision_time = pd.Timestamp("2014-04-02T23:00:00+00:00")

    history = crop_history_for_coldstart(series, first_decision_time, 7)

    # 7 Tage inklusive Vortag, über die Umstellung am 30.03. also 167 statt 168 Stunden
    assert history.index[0] == pd.Timestamp("2014-03-27T00:00:00+00:00")
    assert len(history.loc[: first_decision_time - pd.Timedelta(hours=1)]) == 167
