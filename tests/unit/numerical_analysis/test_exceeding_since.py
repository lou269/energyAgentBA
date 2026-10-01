# python -m pytest tests/unit/numerical_analysis/test_exceeding_since.py -v

import pandas as pd

from src.numerical_analysis.anomaly_detection import exceeding_since


def _scores(values: list[float]) -> pd.Series:
    index = pd.date_range("2014-03-01", periods=len(values), freq="1D", tz="UTC")
    return pd.Series(values, index=index)


def _since(values: list[float]) -> pd.Timestamp | None:
    return exceeding_since(
        _scores(values), threshold=1.0, max_gap_days=1, local_timezone="Europe/London"
    )


def test_one_gap_keeps_run() -> None:
    scores = _scores([2.0, 2.0, 0.0, 2.0, 2.0])

    assert _since([2.0, 2.0, 0.0, 2.0, 2.0]) == scores.index[0]


def test_two_gaps_restart() -> None:
    scores = _scores([2.0, 2.0, 0.0, 0.0, 2.0])

    assert _since([2.0, 2.0, 0.0, 0.0, 2.0]) == scores.index[4]


def test_last_hit_age() -> None:
    scores = _scores([2.0, 2.0, 2.0, 0.0])

    assert _since([2.0, 2.0, 2.0, 0.0]) == scores.index[0]
    assert _since([2.0, 2.0, 2.0, 0.0, 0.0]) is None


def test_direction_change() -> None:
    scores = _scores([-2.0, 2.0, 2.0])

    assert _since([-2.0, 2.0, 2.0]) == scores.index[1]
