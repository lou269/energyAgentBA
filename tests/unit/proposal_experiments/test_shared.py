# python -m pytest tests/unit/proposal_experiments/test_shared.py -v

import pandas as pd

from experiments.proposal_experiments.shared import build_decision_times, subtract_channels_in_window


def test_build_decision_times_applies_margins_on_both_sides() -> None:
    window_start = pd.Timestamp("2020-06-06T00:00:00+00:00")
    window_end = pd.Timestamp("2020-06-13T00:00:00+00:00")

    decision_times = build_decision_times(
        window_start, window_end, margin_before_days=7, margin_after_days=4, local_timezone="UTC"
    )

    assert decision_times[0] == window_start - pd.Timedelta(days=7)
    assert decision_times[-1] == window_end + pd.Timedelta(days=4)
    assert all(second - first == pd.Timedelta(hours=24) for first, second in zip(decision_times, decision_times[1:]))


def test_build_decision_times_stay_on_local_midnight_across_dst() -> None:
    # Mitternacht BST, 60 Tage davor ist noch GMT
    cutover = pd.Timestamp("2014-04-15", tz="Europe/London").tz_convert("UTC")

    decision_times = build_decision_times(
        cutover, cutover, margin_before_days=60, margin_after_days=0, local_timezone="Europe/London"
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

    adjusted = subtract_channels_in_window(mains, appliance, ["H1_M5"], window_start=window_start, window_end=window_end)

    assert (adjusted.loc[window_start : window_end - pd.Timedelta(hours=1)] == 250.0).all()
    assert (adjusted.loc[:window_start].iloc[:-1] == 300.0).all()
    assert (adjusted.loc[window_end:] == 300.0).all()
    


def test_subtract_channels_in_window_clips_at_zero() -> None:
    mains = _mains(24, value=30.0)
    appliance = pd.DataFrame({"H1_M5": 50.0}, index=mains.index)
    window_start, window_end = mains.index[0], mains.index[-1]

    adjusted = subtract_channels_in_window(mains, appliance, ["H1_M5"], window_start=window_start, window_end=window_end)

    assert (adjusted.loc[window_start : window_end - pd.Timedelta(hours=1)] == 0.0).all()