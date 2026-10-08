import numpy as np
import pandas as pd

from experiments.k1_detection.k1_chain import run_chain
from src.config.config_forecasting import NumericalAnalysisConfig


def _noisy_step_series() -> pd.Series:
    # Tagesniveau um 200 W mit Streuung, ab Tag 80 dreimal so hoch
    rng = np.random.default_rng(0)
    levels = rng.normal(200.0, 25.0, 140)
    levels[80:] *= 3
    index = pd.date_range("2020-01-01", periods=24 * 140, freq="1h", tz="UTC")
    return pd.Series(np.repeat(levels, 24), index=index)


def test_chain_reset() -> None:
    series = _noisy_step_series()
    days = pd.date_range("2020-03-01", periods=80)

    chain = run_chain(
        series,
        days,
        NumericalAnalysisConfig(),
        cache={},
        local_timezone="UTC",
        calendar_lookback_days=7,
        calendar_lookahead_days=7,
    )
    reset_days = chain.loc[chain["reset"], "analyzed_day"]

    assert len(reset_days) >= 1
    # Tag 80 ist der 21.03.2020
    assert reset_days.min() >= pd.Timestamp("2020-03-21")
