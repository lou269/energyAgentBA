# python -m pytest tests/unit/experiments/e1_new_device -v

import numpy as np
import pandas as pd
import pytest

from experiments.e1_new_device.e1_scenarios import hide_device_before_cutover


DEVICE_METER_KEY = "H1_M5"


def _mains(hours: int) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    hour_of_day = index.hour.to_numpy()
    values = 200.0 + 50.0 * np.sin(2 * np.pi * hour_of_day / 24) + 10.0
    return pd.Series(values, index=index, name="target")


def _device(hours: int, *, load_w: float = 30.0) -> pd.Series:
    # Gerät läuft real jeden Tag um Mitternacht, ist also schon im Mains-Rohsignal enthalten
    index = pd.date_range("2024-01-01", periods=hours, freq="1h", tz="UTC")
    values = np.where(index.hour == 0, load_w, 0.0)
    return pd.Series(values, index=index, name=DEVICE_METER_KEY)


def test_before_cutover_device_load_is_subtracted_from_mains() -> None:
    mains = _mains(240)
    device = _device(240)
    cutover_time = mains.index[100]

    target_series = hide_device_before_cutover(
        mains, device.to_frame(), [DEVICE_METER_KEY], cutover_time
    )

    before = mains.index[
        96
    ]  # aktive Gerätestunde (Tag 4, 00:00), liegt vor dem Cutover
    assert device.loc[before] > 0.0
    assert target_series.loc[before] == pytest.approx(
        mains.loc[before] - device.loc[before]
    )


def test_at_and_after_cutover_mains_is_left_unchanged() -> None:
    mains = _mains(240)
    device = _device(240)
    cutover_time = mains.index[
        96
    ]  # selbst eine aktive Gerätestunde -> prüft die Inklusiv-Grenze direkt

    target_series = hide_device_before_cutover(
        mains, device.to_frame(), [DEVICE_METER_KEY], cutover_time
    )

    for timestamp in (cutover_time, mains.index[120]):
        assert device.loc[timestamp] > 0.0
        assert target_series.loc[timestamp] == pytest.approx(mains.loc[timestamp])
