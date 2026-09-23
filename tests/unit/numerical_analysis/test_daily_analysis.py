import pandas as pd

from src.numerical_analysis.daily_analysis import compute_reference_window_end



def _hourly(start, count: int) -> pd.Series:
    index = pd.date_range(start, periods=count, freq="1h", tz="UTC")
    return pd.Series([100.0] * count, index=index, name="target")


def test_compute_reference_window_end_returns_none_below_reference_window_days() -> None:
    history = _hourly("2024-01-01", 48)

    assert compute_reference_window_end(history, local_timezone="UTC", max_growth_days=60, reference_window_days=3) is None


def test_compute_reference_window_end_grows_with_history_up_to_the_cap() -> None:
    history = _hourly("2024-01-01", 24 * 10)

    end = compute_reference_window_end(history, local_timezone="UTC", max_growth_days=60, reference_window_days=3)
    assert end == pd.Timestamp("2024-01-08", tz="UTC")

    # über die Wachstumsgrenze hinaus, statt mit history weiterzuwachsen: Tag 60 ist der 29.02., Fenster beginnt 2 Tage davor
    long_history = _hourly("2024-01-01", 24 * 90)
    capped_end = compute_reference_window_end(long_history, local_timezone="UTC", max_growth_days=60, reference_window_days=3)
    assert capped_end == pd.Timestamp("2024-02-27", tz="UTC")


def test_compute_reference_window_end_without_cap_keeps_growing() -> None:
    long_history = _hourly("2024-01-01", 24 * 90)

    end = compute_reference_window_end(long_history, local_timezone="UTC", max_growth_days=None, reference_window_days=3)
    assert end == pd.Timestamp("2024-03-28", tz="UTC")