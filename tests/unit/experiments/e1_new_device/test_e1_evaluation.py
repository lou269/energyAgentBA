# python -m pytest tests/unit/experiments/e1_new_device/test_e1_evaluation.py -v

import numpy as np
import pandas as pd
import pytest

from experiments.e1_new_device.e1_evaluation import summarize_device_window


def test_device_window_share_after_and_coverage_before() -> None:
    index = pd.date_range("2015-02-27", periods=96, freq="1h", tz="UTC")
    mains = pd.Series(200.0, index=index)
    devices = pd.DataFrame({"H1_M5": 50.0, "H1_M6": 0.0}, index=index)
    # Waschtrockner fehlt vor dem Cutover einen halben Tag, Spülmaschine nie
    devices.iloc[:12, 0] = np.nan

    window = summarize_device_window(
        devices,
        ("H1_M5", "H1_M6"),
        mains,
        pd.Timestamp("2015-03-01", tz="UTC"),
        days_after=1,
    )

    assert window["device_mean_w"] == 50.0
    assert window["device_share_pct"] == 25.0
    assert window["coverage_before_pct"] == pytest.approx(75.0)
    assert window["coverage_after_pct"] == 100.0
