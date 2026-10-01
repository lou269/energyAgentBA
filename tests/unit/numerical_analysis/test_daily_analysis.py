# python -m pytest tests/unit/numerical_analysis/test_daily_analysis.py -v

import numpy as np
import pandas as pd

from src.config.config_forecasting import NumericalAnalysisConfig
from src.numerical_analysis.daily_analysis import compute_analysis_row


def _history(day_levels: list[float]) -> pd.Series:
    index = pd.date_range(
        "2024-01-01", periods=24 * len(day_levels), freq="1h", tz="UTC"
    )
    values = [level for level in day_levels for _ in range(24)]
    return pd.Series(values, index=index, name="target")


def test_analysis_row_none_for_one_day() -> None:
    history = _history([100.0])

    row = compute_analysis_row(
        history,
        target_timestamp=history.index[0],
        config=NumericalAnalysisConfig(),
        local_timezone="UTC",
    )

    assert row is None


def test_analysis_row_flags_jump() -> None:
    noise = np.random.default_rng(3).normal(0.0, 5.0, 70)
    levels = [100.0 + n for n in noise]
    levels[-1] += 100.0
    history = _history(levels)

    row = compute_analysis_row(
        history,
        target_timestamp=history.index[-1].normalize(),
        config=NumericalAnalysisConfig(),
        local_timezone="UTC",
    )

    assert row is not None
    assert row["anomaly_level"] == "unusual"
    assert row["anomaly_direction"] == "high"
    assert row["dominant_scale"] == "weekday"
    assert row["timestamp"] == history.index[-1].normalize()
