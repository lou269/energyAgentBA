import pandas as pd

from src.numerical_analysis.daily_analysis import compute_reference_window_end



def _hourly(start, count: int) -> pd.Series:
    index = pd.date_range(start, periods=count, freq="1h", tz="UTC")
    return pd.Series([100.0] * count, index=index, name="target")


def test_compute_reference_window_end_returns_none_below_reference_window_hours() -> None:
    history = _hourly("2024-01-01", 71)

    assert compute_reference_window_end(history, local_timezone="UTC", max_growth_days=60, reference_window_hours=72) is None


def test_compute_reference_window_end_grows_with_history_up_to_the_cap() -> None:
    history = _hourly("2024-01-01", 24 * 10)

    end = compute_reference_window_end(history, local_timezone="UTC", max_growth_days=60, reference_window_hours=72)
    assert end == history.index[-1] - pd.Timedelta(hours=71)

    # über die Wachstumsgrenze hinaus, statt mit history weiterzuwachsen
    long_history = _hourly("2024-01-01", 24 * 90)
    capped_end = compute_reference_window_end(long_history, local_timezone="UTC", max_growth_days=60, reference_window_hours=72)
    growth_ceiling = long_history.index[0].normalize() + pd.DateOffset(days=60)
    assert capped_end == growth_ceiling - pd.Timedelta(hours=71)