# python -m pytest tests/unit/preprocessing/test_split.py -v

import pandas as pd
import pytest

from src.common import windows
from src.config.config_forecasting import SplitDefinition
from src.preprocessing.split import split_index


@pytest.fixture(autouse=True)
def small_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    splits = {
        "train": SplitDefinition(window="development", days=6),
        "validation": SplitDefinition(window="development", days=None),
        "test": SplitDefinition(window="test", days=None),
    }
    monkeypatch.setattr(windows, "SPLITS", splits)


def test_split_cuts_on_local_calendar_days_not_on_row_count() -> None:
    # stündliche Auflösung, 10 volle Tage, Cutoff muss trotzdem an Tagesgrenzen liegen
    index = pd.date_range("2020-01-01T00:00:00Z", periods=10 * 24, freq="1h")

    train = split_index(index, "development", "train", "UTC")
    validation = split_index(index, "development", "validation", "UTC")

    assert len(train) == 6 * 24
    assert len(validation) == 4 * 24
    assert train[-1].hour == 23
    assert validation[0].hour == 0


def test_split_uses_local_days_when_utc_and_local_midnight_diverge() -> None:
    index = pd.date_range("2020-01-01T05:00:00Z", periods=10 * 24, freq="1h")

    train = split_index(index, "development", "train", "America/New_York")
    validation = split_index(index, "development", "validation", "America/New_York")

    assert train[-1].tz_convert("America/New_York").hour == 23
    assert validation[0].tz_convert("America/New_York").hour == 0
